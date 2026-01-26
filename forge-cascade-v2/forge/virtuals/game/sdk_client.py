"""
GAME SDK Client for Virtuals Protocol

This module provides the integration layer between Forge and the Virtuals
Protocol GAME (Generative Autonomous Multimodal Entities) framework. The
GAME framework is the decision-making engine that powers autonomous AI agents.

The GAME architecture consists of three main components:
1. Task Generator (High-Level Planner) - Determines what the agent should do
2. Workers (Low-Level Planners) - Execute specific types of tasks
3. Functions - The actual actions workers can take

This client wraps the official GAME SDK and provides Forge-specific
functionality for creating knowledge agents, overlay agents, and
governance advisors.
"""

import asyncio
import logging
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime, timedelta
from typing import Any, Union

import httpx

from ..config import VirtualsConfig, get_virtuals_config
from ..models import (
    AgentGoals,
    AgentPersonality,
    AgentStatus,
    ForgeAgent,
    ForgeAgentCreate,
    WorkerDefinition,
)

logger = logging.getLogger(__name__)


class GAMEClientError(Exception):
    """Base exception for GAME SDK client errors."""
    pass


class AuthenticationError(GAMEClientError):
    """Raised when API authentication fails."""
    pass


class RateLimitError(GAMEClientError):
    """Raised when API rate limit is exceeded."""
    pass


class AgentNotFoundError(GAMEClientError):
    """Raised when an agent is not found."""
    pass


class FunctionDefinition:
    """
    Definition of a function that a GAME worker can execute.

    Functions are the atomic actions that agents can perform. They include
    metadata about arguments, return types, and the actual executable code.

    In Forge, functions typically wrap operations like:
    - Querying knowledge capsules
    - Running overlay analyses
    - Participating in governance votes
    - Interacting with external services
    """

    def __init__(
        self,
        name: str,
        description: str,
        arguments: list[dict[str, Any]],
        executable: Union[
            Callable[..., tuple[str, Any, dict[str, Any]]],
            Callable[..., Coroutine[Any, Any, tuple[str, Any, dict[str, Any]]]],
        ],
        returns_description: str = "",
    ) -> None:
        """
        Initialize a function definition.

        Args:
            name: Unique function name (snake_case recommended)
            description: Natural language description for the LLM
            arguments: List of argument definitions with name, type, description
            executable: The actual Python function to call. Must return
                       (status, result, state_update) tuple.
            returns_description: Description of return value
        """
        self.name = name
        self.description = description
        self.arguments = arguments
        self.executable = executable
        self.returns_description = returns_description

    def to_game_format(self) -> dict[str, Any]:
        """Convert to GAME SDK function format."""
        return {
            "fn_name": self.name,
            "fn_description": self.description,
            "args": [
                {
                    "name": arg["name"],
                    "type": arg.get("type", "string"),
                    "description": arg.get("description", ""),
                }
                for arg in self.arguments
            ],
        }

    async def execute(self, **kwargs: Any) -> tuple[str, Any, dict[str, Any]]:
        """
        Execute the function with given arguments.

        Returns:
            Tuple of (status, result, state_update) where:
            - status: "DONE", "FAILED", or "PENDING"
            - result: The function's return value
            - state_update: Dict of state changes to apply
        """
        if asyncio.iscoroutinefunction(self.executable):
            result: tuple[str, Any, dict[str, Any]] = await self.executable(**kwargs)
            return result
        else:
            sync_result: tuple[str, Any, dict[str, Any]] = self.executable(**kwargs)  # type: ignore[assignment]
            return sync_result


class GAMEWorker:
    """
    A GAME worker (Low-Level Planner) that handles specific types of tasks.

    Workers are specialized components within an agent. Each worker has a
    defined set of functions it can execute and maintains its own state.
    The Task Generator routes tasks to appropriate workers based on their
    descriptions and capabilities.

    For Forge, workers might specialize in:
    - Knowledge retrieval and search
    - Security analysis and validation
    - Governance participation
    - External API interactions
    """

    def __init__(
        self,
        worker_id: str,
        description: str,
        functions: list[FunctionDefinition],
        get_state_fn: Callable[..., dict[str, Any]] | None = None,
    ):
        """
        Initialize a GAME worker.

        Args:
            worker_id: Unique identifier for this worker
            description: Natural language description of worker's capabilities
            functions: List of functions this worker can execute
            get_state_fn: Optional function to retrieve worker's current state.
                         Called with (last_function_result, current_state) and
                         should return a dict representing the new state.
        """
        self.worker_id = worker_id
        self.description = description
        self.functions = {f.name: f for f in functions}
        self._get_state_fn = get_state_fn or self._default_get_state
        self._state: dict[str, Any] = {}

    def _default_get_state(self, function_result: Any, current_state: dict[str, Any]) -> dict[str, Any]:
        """Default state function returns current state unchanged."""
        return current_state

    def get_state(self, function_result: Any = None) -> dict[str, Any]:
        """Get the current worker state, optionally updating based on function result."""
        self._state = self._get_state_fn(function_result, self._state)
        return self._state

    def to_game_format(self) -> dict[str, Any]:
        """Convert to GAME SDK worker configuration format."""
        return {
            "id": self.worker_id,
            "worker_description": self.description,
            "action_space": [f.to_game_format() for f in self.functions.values()],
        }

    async def execute_function(self, function_name: str, **kwargs: Any) -> tuple[str, Any, dict[str, Any]]:
        """Execute a function on this worker."""
        if function_name not in self.functions:
            raise GAMEClientError(f"Function {function_name} not found on worker {self.worker_id}")
        return await self.functions[function_name].execute(**kwargs)


class GAMESDKClient:
    """
    Client for interacting with the Virtuals Protocol GAME SDK.

    This client handles all communication with the GAME API, including:
    - Authentication and token management
    - Agent creation and configuration
    - Task execution and state management
    - Memory synchronization

    The client implements the GAME SDK's polling/execution model, where
    agents continuously request planning decisions from the API and
    execute the resulting actions locally.
    """

    def __init__(self, config: VirtualsConfig | None = None):
        """
        Initialize the GAME SDK client.

        Args:
            config: Optional configuration. Uses global config if not provided.
        """
        self.config = config or get_virtuals_config()
        self._access_token: str | None = None
        self._token_expires: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._rate_limit_remaining = self.config.game_api_rate_limit
        self._rate_limit_reset: datetime | None = None

    async def initialize(self) -> None:
        """
        Initialize the HTTP client and authenticate with the GAME API.

        This method establishes the HTTP connection and exchanges the API key
        for an access token that's used for subsequent API calls. The access
        token is refreshed automatically when it expires.
        """
        self._http_client = httpx.AsyncClient(
            base_url=self.config.api_base_url,
            timeout=30.0,
        )

        # Authenticate if API key is configured
        if self.config.api_key:
            await self._authenticate()
            logger.info("GAME SDK client initialized and authenticated")
        else:
            logger.warning(
                "GAME SDK client initialized without API key. "
                "Agent features will be limited."
            )

    async def close(self) -> None:
        """Close the HTTP client and cleanup resources."""
        if self._http_client:
            await self._http_client.aclose()
        self._http_client = None
        self._access_token = None

    async def _authenticate(self) -> None:
        """
        Exchange API key for access token.

        The GAME API uses a two-step authentication process:
        1. POST to /api/accesses/tokens with API key in X-API-KEY header
        2. Receive access token to use as Bearer token for subsequent requests

        Access tokens have limited validity and must be refreshed.
        """
        if not self.config.api_key:
            raise AuthenticationError("API key not configured")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config.auth_url,
                    headers={"X-API-KEY": self.config.api_key},
                )
                response.raise_for_status()
                data = response.json()

                self._access_token = data["data"]["accessToken"]
                # Assume token expires in 1 hour (typical for such systems)
                self._token_expires = datetime.now(UTC) + timedelta(hours=1)

                logger.debug("Authenticated with GAME API")

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError("Invalid API key")
            raise GAMEClientError(f"Authentication failed: {e}")

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid access token, refreshing if necessary."""
        if not self._access_token:
            await self._authenticate()
        elif self._token_expires and datetime.now(UTC) >= self._token_expires:
            await self._authenticate()

    def _get_auth_headers(self) -> dict[str, str]:
        """Get headers with authentication token."""
        if not self._access_token:
            return {}
        return {"Authorization": f"Bearer {self._access_token}"}

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Make an authenticated request to the GAME API.

        This method handles rate limiting, authentication refresh, and
        error handling for all API requests.
        """
        await self._ensure_authenticated()

        # Check rate limit
        if self._rate_limit_remaining <= 0:
            if self._rate_limit_reset and datetime.now(UTC) < self._rate_limit_reset:
                wait_time = (self._rate_limit_reset - datetime.now(UTC)).total_seconds()
                raise RateLimitError(
                    f"Rate limit exceeded. Retry after {wait_time:.0f} seconds"
                )
            # Reset rate limit counter
            self._rate_limit_remaining = self.config.game_api_rate_limit

        headers = kwargs.pop("headers", {})
        headers.update(self._get_auth_headers())

        if self._http_client is None:
            raise GAMEClientError("HTTP client not initialized. Call initialize() first.")

        try:
            response = await self._http_client.request(
                method,
                endpoint,
                headers=headers,
                **kwargs
            )

            # Update rate limit tracking from response headers
            if "X-RateLimit-Remaining" in response.headers:
                self._rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
            if "X-RateLimit-Reset" in response.headers:
                reset_timestamp = int(response.headers["X-RateLimit-Reset"])
                self._rate_limit_reset = datetime.fromtimestamp(reset_timestamp)

            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                raise RateLimitError("Rate limit exceeded")
            elif e.response.status_code == 401:
                # FIX: Add recursion guard to prevent infinite loop on auth failure
                # Check if this is already a retry attempt
                if kwargs.get("_auth_retry"):
                    raise AuthenticationError("Authentication failed after retry")
                # Token may have expired, try to refresh
                await self._authenticate()
                kwargs["_auth_retry"] = True
                return await self._make_request(method, endpoint, **kwargs)
            elif e.response.status_code == 404:
                raise AgentNotFoundError(f"Resource not found: {endpoint}")
            else:
                raise GAMEClientError(f"API request failed: {e}")

    # ==================== Agent Management ====================

    async def create_agent(
        self,
        create_request: ForgeAgentCreate,
        workers: list[GAMEWorker],
    ) -> ForgeAgent:
        """
        Create a new agent on the GAME platform.

        This method registers an agent with the GAME framework, setting up
        its personality, goals, and worker configuration. The agent can then
        be started to begin autonomous operation.

        Args:
            create_request: The agent creation specification
            workers: List of GAMEWorker instances defining the agent's capabilities

        Returns:
            The created ForgeAgent with GAME framework IDs assigned
        """
        # Build the agent configuration for the GAME API
        agent_config = {
            "name": create_request.name,
            "goal": create_request.goals.primary_goal,
            "description": create_request.personality.to_game_prompt(),
            "workers": [w.to_game_format() for w in workers],
        }

        try:
            response = await self._make_request(
                "POST",
                "/agents",
                json=agent_config,
            )

            game_agent_id = response.get("data", {}).get("agentId")

            # Create the ForgeAgent model
            agent = ForgeAgent(
                name=create_request.name,
                personality=create_request.personality,
                goals=create_request.goals,
                status=AgentStatus.PROTOTYPE,
                forge_overlay_id=create_request.forge_overlay_id,
                forge_capsule_ids=create_request.forge_capsule_ids,
                workers=[
                    WorkerDefinition(
                        id=w.worker_id,
                        name=w.worker_id,
                        description=w.description,
                        function_names=list(w.functions.keys()),
                    )
                    for w in workers
                ],
                memory_config=create_request.memory_config,
                game_agent_id=game_agent_id,
                primary_chain=create_request.primary_chain,
            )

            logger.info(f"Created agent {agent.id} (GAME ID: {game_agent_id})")
            return agent

        except GAMEClientError:
            raise
        except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as e:
            raise GAMEClientError(f"Failed to create agent: {e}")

    async def get_agent(self, agent_id: str) -> ForgeAgent | None:
        """
        Get agent details from the GAME platform.

        This retrieves the current state and configuration of an agent
        from the GAME framework.
        """
        try:
            await self._make_request("GET", f"/agents/{agent_id}")
            # Transform response to ForgeAgent model
            # This would need mapping from GAME API response format
            return None  # Placeholder - implement based on actual API response
        except AgentNotFoundError:
            return None

    async def update_agent(
        self,
        agent_id: str,
        personality: AgentPersonality | None = None,
        goals: AgentGoals | None = None,
    ) -> ForgeAgent:
        """
        Update an existing agent's configuration.

        Note: Some properties (name, tokenization) cannot be changed after creation.
        """
        update_data = {}

        if personality:
            update_data["description"] = personality.to_game_prompt()
        if goals:
            update_data["goal"] = goals.primary_goal

        await self._make_request(
            "PATCH",
            f"/agents/{agent_id}",
            json=update_data,
        )

        # Return updated agent
        agent = await self.get_agent(agent_id)
        if agent is None:
            raise AgentNotFoundError(f"Agent {agent_id} not found after update")
        return agent

    async def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent from the GAME platform.

        Warning: This is irreversible. Tokenized agents may have additional
        restrictions on deletion.
        """
        try:
            await self._make_request("DELETE", f"/agents/{agent_id}")
            logger.info(f"Deleted agent {agent_id}")
            return True
        except AgentNotFoundError:
            return False

    # ==================== Agent Execution ====================

    async def get_next_action(
        self,
        agent_id: str,
        current_state: dict[str, Any],
        context: str | None = None,
    ) -> dict[str, Any]:
        """
        Get the next action the agent should take.

        This is the core of the GAME framework's planning loop. The API
        analyzes the agent's current state and context, then returns
        the next action (worker + function + arguments) to execute.

        Args:
            agent_id: The agent's GAME framework ID
            current_state: Current state from all workers
            context: Optional additional context or user input

        Returns:
            Dict containing:
            - worker_id: Which worker should handle this
            - function_name: Which function to call
            - arguments: Arguments for the function
            - reasoning: The LLM's reasoning for this action
        """
        request_data = {
            "agentId": agent_id,
            "state": current_state,
        }

        if context:
            request_data["context"] = context

        response = await self._make_request(
            "POST",
            "/agents/plan",
            json=request_data,
        )

        result: dict[str, Any] = response.get("data", {})
        return result

    async def run_agent_loop(
        self,
        agent: ForgeAgent,
        workers: dict[str, GAMEWorker],
        context: str | None = None,
        max_iterations: int = 10,
        stop_condition: Callable[[dict[str, Any]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Run the agent's autonomous decision loop.

        This method implements the continuous planning-execution cycle:
        1. Gather current state from all workers
        2. Request next action from GAME API
        3. Execute the action via the appropriate worker
        4. Update state and repeat

        The loop continues until max_iterations is reached, a stop condition
        is met, or the agent decides it has completed its task.

        Args:
            agent: The ForgeAgent to run
            workers: Dict mapping worker_id to GAMEWorker instances
            context: Initial context or user query
            max_iterations: Maximum number of action cycles
            stop_condition: Optional function that receives action result and
                           returns True to stop the loop

        Returns:
            List of action results from each iteration
        """
        if not agent.game_agent_id:
            raise GAMEClientError("Agent not registered with GAME framework")

        results: list[dict[str, Any]] = []

        for iteration in range(max_iterations):
            # Gather state from all workers
            current_state = {}
            for worker_id, worker in workers.items():
                last_result = results[-1] if results else None
                current_state[worker_id] = worker.get_state(last_result)

            # Get next action from GAME API
            try:
                action = await self.get_next_action(
                    agent.game_agent_id,
                    current_state,
                    context if iteration == 0 else None,  # Context only on first iteration
                )
            except RateLimitError:
                logger.warning("Rate limited, waiting before retry...")
                await asyncio.sleep(30)
                continue

            # Check if agent is done
            if action.get("done", False):
                logger.info(f"Agent {agent.id} completed task")
                break

            # Execute the action
            target_worker_id: str | None = action.get("worker_id")
            function_name: str | None = action.get("function_name")
            arguments: dict[str, Any] = action.get("arguments", {})

            if target_worker_id is None or target_worker_id not in workers:
                logger.error(f"Unknown worker: {target_worker_id}")
                continue

            if function_name is None:
                logger.error("No function_name in action")
                continue

            try:
                status, result, state_update = await workers[target_worker_id].execute_function(
                    function_name,
                    **arguments
                )

                action_result = {
                    "iteration": iteration,
                    "worker_id": target_worker_id,
                    "function_name": function_name,
                    "arguments": arguments,
                    "status": status,
                    "result": result,
                    "state_update": state_update,
                    "reasoning": action.get("reasoning", ""),
                }
                results.append(action_result)

                logger.debug(
                    f"Agent {agent.id} iteration {iteration}: "
                    f"{worker_id}.{function_name} -> {status}"
                )

                # Check stop condition
                if stop_condition and stop_condition(action_result):
                    break

            except (GAMEClientError, ConnectionError, TimeoutError, OSError, ValueError, RuntimeError, KeyError, TypeError) as e:
                logger.error(f"Action execution failed: {e}")
                results.append({
                    "iteration": iteration,
                    "worker_id": target_worker_id,
                    "function_name": function_name,
                    "status": "FAILED",
                    "error": str(e),
                })

        return results

    # ==================== Memory Operations ====================

    async def store_memory(
        self,
        agent_id: str,
        memory_type: str,
        content: dict[str, Any],
        ttl_days: int | None = None,
    ) -> str:
        """
        Store a memory for an agent.

        Memories persist across sessions and can be retrieved by the agent
        during future interactions. This enables continuity and learning.

        Args:
            agent_id: The agent to store memory for
            memory_type: Category of memory (conversation, fact, preference, etc.)
            content: The memory content to store
            ttl_days: Optional time-to-live in days

        Returns:
            The ID of the stored memory
        """
        memory_data = {
            "agentId": agent_id,
            "type": memory_type,
            "content": content,
        }

        if ttl_days:
            memory_data["ttlDays"] = ttl_days  # type: ignore[assignment]

        response = await self._make_request(
            "POST",
            "/memories",
            json=memory_data,
        )

        memory_id: str = response.get("data", {}).get("memoryId", "")
        return memory_id

    async def retrieve_memories(
        self,
        agent_id: str,
        query: str,
        memory_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Retrieve relevant memories for an agent.

        Uses semantic search to find memories relevant to the query.

        Args:
            agent_id: The agent to retrieve memories for
            query: Search query for semantic matching
            memory_type: Optional filter by memory type
            limit: Maximum memories to return

        Returns:
            List of memory objects with content and metadata
        """
        params: dict[str, Any] = {
            "agentId": agent_id,
            "query": query,
            "limit": limit,
        }

        if memory_type:
            params["type"] = memory_type

        response = await self._make_request(
            "GET",
            "/memories/search",
            params=params,
        )

        memories: list[dict[str, Any]] = response.get("data", {}).get("memories", [])
        return memories


# Global client instance
_game_client: GAMESDKClient | None = None


async def get_game_client() -> GAMESDKClient:
    """
    Get the global GAME SDK client instance.

    Initializes the client if not already done.
    """
    global _game_client
    if _game_client is None:
        _game_client = GAMESDKClient()
        await _game_client.initialize()
    return _game_client
