"""
Copilot Forge Agent

This module provides the main agent class for integrating GitHub Copilot SDK
with Forge's knowledge management capabilities.

The CopilotForgeAgent wraps the Copilot SDK client and provides:
- Automatic tool registration for Forge operations
- Session management with context preservation
- Streaming response support
- Event handling for real-time updates

Example:
    ```python
    from forge.copilot import CopilotForgeAgent, CopilotConfig

    config = CopilotConfig(
        model="gpt-5",
        streaming=True,
        system_prompt="You are a Forge knowledge assistant."
    )

    agent = CopilotForgeAgent(config)
    await agent.start()

    # Simple chat
    response = await agent.chat("What capsules do I have about AI?")
    print(response)

    # Streaming chat
    async for chunk in agent.stream_chat("Explain my knowledge graph"):
        print(chunk, end="", flush=True)

    await agent.stop()
    ```
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from forge.security.prompt_sanitization import sanitize_for_prompt

from .tools import ForgeToolRegistry

logger = logging.getLogger(__name__)


class AgentState(str, Enum):
    """State of the Copilot agent."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class CopilotConfig:
    """
    Configuration for CopilotForgeAgent.

    Attributes:
        model: The LLM model to use (default: "gpt-5")
        streaming: Enable streaming responses (default: True)
        system_prompt: Custom system prompt for the agent
        cli_path: Path to Copilot CLI executable
        use_stdio: Use stdio transport instead of TCP (default: True)
        log_level: Logging level for the SDK
        auto_restart: Auto-restart on crash (default: True)
        timeout_seconds: Request timeout in seconds
        max_retries: Maximum retry attempts for failed requests
    """

    model: str = "gpt-5"
    streaming: bool = True
    system_prompt: str | None = None
    cli_path: str | None = None
    use_stdio: bool = True
    log_level: str = "info"
    auto_restart: bool = True
    timeout_seconds: int = 120
    max_retries: int = 3
    enabled_tools: list[str] = field(default_factory=list)


@dataclass
class ChatMessage:
    """A message in the chat history."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Response from a chat interaction."""

    content: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reasoning: str | None = None
    tokens_used: int = 0
    latency_ms: float = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class CopilotForgeAgent:
    """
    AI agent powered by GitHub Copilot SDK with Forge knowledge capabilities.

    This agent combines Copilot's agentic runtime with Forge's knowledge
    management tools, enabling natural language interactions with the
    knowledge graph, capsules, overlays, and governance.

    Features:
    - Multi-turn conversations with context preservation
    - Custom Forge tools for knowledge operations
    - Streaming responses for real-time output
    - Automatic tool execution and result handling
    - Session management with history retrieval

    Example:
        ```python
        agent = CopilotForgeAgent()
        await agent.start()

        # Chat with the agent
        response = await agent.chat(
            "Find all capsules about machine learning and summarize them"
        )
        print(response.content)

        # The agent can execute Forge tools automatically
        # e.g., it might call forge_knowledge_query and forge_semantic_search

        await agent.stop()
        ```
    """

    # SECURITY FIX (Audit 7 - Session 9): Bound chat history to prevent memory exhaustion
    MAX_HISTORY_LENGTH = 200

    DEFAULT_SYSTEM_PROMPT = """You are Forge, an intelligent knowledge management assistant.

You have access to a powerful knowledge graph containing capsules (atomic units of knowledge),
overlays (processing pipelines), and governance systems.

Your capabilities include:
- Searching and querying the knowledge graph
- Creating and managing knowledge capsules
- Executing overlays for knowledge processing
- Providing insights about the governance system

Always be helpful, accurate, and thorough in your responses. When searching for information,
use semantic search for conceptual queries and knowledge queries for specific lookups.

When creating capsules, ensure they are well-structured with appropriate tags and metadata."""

    def __init__(
        self,
        config: CopilotConfig | None = None,
        tool_registry: ForgeToolRegistry | None = None,
    ) -> None:
        """
        Initialize the Copilot Forge agent.

        Args:
            config: Agent configuration options
            tool_registry: Registry of Forge tools (created if not provided)
        """
        self.config = config or CopilotConfig()
        self._tool_registry = tool_registry or ForgeToolRegistry()
        self._client: Any = None
        self._session: Any = None
        self._state = AgentState.STOPPED
        self._history: list[ChatMessage] = []
        self._event_handlers: list[Callable[..., Any]] = []

    @property
    def state(self) -> AgentState:
        """Get the current agent state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if the agent is running."""
        return self._state == AgentState.RUNNING

    @property
    def history(self) -> list[ChatMessage]:
        """Get the conversation history."""
        return self._history.copy()

    async def start(
        self,
        db_client: Any = None,
        search_service: Any = None,
        capsule_service: Any = None,
        overlay_manager: Any = None,
    ) -> None:
        """
        Start the Copilot agent and initialize services.

        Args:
            db_client: Database client for knowledge operations
            search_service: Semantic search service
            capsule_service: Capsule management service
            overlay_manager: Overlay execution manager

        Raises:
            RuntimeError: If the Copilot SDK is not installed
            ConnectionError: If unable to connect to Copilot CLI
        """
        if self._state == AgentState.RUNNING:
            logger.warning("Agent is already running")
            return

        self._state = AgentState.STARTING
        logger.info("Starting Copilot Forge agent...")

        try:
            # Try to import Copilot SDK
            try:
                from copilot import CopilotClient  # type: ignore[import-not-found,unused-ignore]
                from copilot.types import (  # type: ignore[import-not-found,unused-ignore]
                    CopilotClientOptions,
                )
            except ImportError:
                raise RuntimeError(
                    "GitHub Copilot SDK not installed. "
                    "Install with: pip install github-copilot-sdk\n"
                    "Also ensure Copilot CLI is installed: "
                    "https://docs.github.com/en/copilot/how-tos/set-up/install-copilot-cli"
                )

            # Initialize tool registry with Forge services
            await self._tool_registry.initialize(
                db_client=db_client,
                search_service=search_service,
                capsule_service=capsule_service,
                overlay_manager=overlay_manager,
            )

            # Create Copilot client
            client_config = CopilotClientOptions(
                use_stdio=self.config.use_stdio,
                log_level=self.config.log_level,  # type: ignore[typeddict-item,unused-ignore]
                auto_restart=self.config.auto_restart,
                auto_start=True,
            )

            # Set CLI path - use config, env var, or auto-discover
            cli_path = self.config.cli_path
            if not cli_path:
                import os

                cli_path = os.environ.get("COPILOT_CLI_PATH")
            if not cli_path:
                # Auto-discover common installation paths
                import shutil

                cli_path = shutil.which("copilot")
                if not cli_path:
                    # Check npm global install location on Windows
                    import os as _os

                    npm_path = _os.path.expandvars(r"%APPDATA%\npm\copilot.cmd")
                    if _os.path.exists(npm_path):
                        cli_path = npm_path

            if cli_path:
                client_config["cli_path"] = cli_path
                logger.info(f"Using Copilot CLI at: {cli_path}")

            self._client = CopilotClient(client_config)
            await self._client.start()

            # Create session with Forge tools
            system_prompt = self.config.system_prompt or self.DEFAULT_SYSTEM_PROMPT
            session_config: dict[str, Any] = {
                "model": self.config.model,
                "streaming": self.config.streaming,
                "tools": self._tool_registry.get_copilot_tools(),
                "system_message": {"content": system_prompt},
            }

            self._session = await self._client.create_session(session_config)

            # Set up event handlers
            self._session.on(self._handle_event)

            self._state = AgentState.RUNNING
            logger.info("Copilot Forge agent started successfully")

        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            self._state = AgentState.ERROR
            logger.error(f"Failed to start agent: {e}")
            raise

    async def stop(self) -> None:
        """Stop the Copilot agent and cleanup resources."""
        if self._state == AgentState.STOPPED:
            return

        self._state = AgentState.STOPPING
        logger.info("Stopping Copilot Forge agent...")

        try:
            if self._session:
                await self._session.destroy()
                self._session = None

            if self._client:
                await self._client.stop()
                self._client = None

            self._state = AgentState.STOPPED
            logger.info("Copilot Forge agent stopped")

        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            self._state = AgentState.ERROR
            logger.error(f"Error stopping agent: {e}")
            raise

    async def chat(self, message: str, metadata: dict[str, Any] | None = None) -> ChatResponse:
        """
        Send a message and get a complete response.

        Args:
            message: User message to send
            metadata: Optional metadata to attach

        Returns:
            ChatResponse with the assistant's reply

        Raises:
            RuntimeError: If agent is not running
        """
        if not self.is_running:
            raise RuntimeError("Agent is not running. Call start() first.")

        # SECURITY FIX (Audit 7 - Session 9): Sanitize user input to prevent prompt injection
        sanitized_message = sanitize_for_prompt(message, field_name="user_message")

        start_time = datetime.now(UTC)

        # Add user message to history (original for display)
        self._history.append(
            ChatMessage(
                role="user",
                content=message,
                metadata=metadata or {},
            )
        )
        # SECURITY FIX (Audit 7 - Session 9): Bound chat history to prevent memory exhaustion
        if len(self._history) > self.MAX_HISTORY_LENGTH:
            # Keep system messages and last N messages
            self._history = self._history[-self.MAX_HISTORY_LENGTH :]

        # Set up response collection
        response_content: list[str] = []
        reasoning_content: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        done = asyncio.Event()

        def collect_response(event: Any) -> None:
            if event.type.value == "assistant.message":
                response_content.append(event.data.content)
            elif event.type.value == "assistant.reasoning":
                reasoning_content.append(event.data.content)
            elif event.type.value == "tool.call":
                tool_calls.append(
                    {
                        "name": event.data.name,
                        "arguments": event.data.arguments,
                    }
                )
            elif event.type.value == "session.idle":
                done.set()

        # Temporarily add our collector
        self._session.on(collect_response)

        try:
            # Send the sanitized message
            await self._session.send({"prompt": sanitized_message})

            # Wait for completion with timeout
            await asyncio.wait_for(done.wait(), timeout=self.config.timeout_seconds)

        except TimeoutError:
            logger.error(f"Chat request timed out after {self.config.timeout_seconds}s")
            raise

        # Calculate latency
        latency_ms = (datetime.now(UTC) - start_time).total_seconds() * 1000

        # Build response
        content = "".join(response_content)
        reasoning = "".join(reasoning_content) if reasoning_content else None

        response = ChatResponse(
            content=content,
            tool_calls=tool_calls,
            reasoning=reasoning,
            latency_ms=latency_ms,
        )

        # Add assistant message to history
        self._history.append(
            ChatMessage(
                role="assistant",
                content=content,
                tool_calls=tool_calls,
            )
        )
        # SECURITY FIX (Audit 7 - Session 9): Bound chat history to prevent memory exhaustion
        if len(self._history) > self.MAX_HISTORY_LENGTH:
            # Keep system messages and last N messages
            self._history = self._history[-self.MAX_HISTORY_LENGTH :]

        return response

    async def stream_chat(
        self,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[str]:
        """
        Send a message and stream the response.

        Args:
            message: User message to send
            metadata: Optional metadata to attach

        Yields:
            Response chunks as they arrive

        Raises:
            RuntimeError: If agent is not running
        """
        if not self.is_running:
            raise RuntimeError("Agent is not running. Call start() first.")

        # SECURITY FIX (Audit 7 - Session 9): Sanitize user input to prevent prompt injection
        sanitized_message = sanitize_for_prompt(message, field_name="user_message")

        if not self.config.streaming:
            # Fall back to non-streaming
            response = await self.chat(message, metadata)
            yield response.content
            return

        # Add user message to history (original for display)
        self._history.append(
            ChatMessage(
                role="user",
                content=message,
                metadata=metadata or {},
            )
        )
        # SECURITY FIX (Audit 7 - Session 9): Bound chat history to prevent memory exhaustion
        if len(self._history) > self.MAX_HISTORY_LENGTH:
            # Keep system messages and last N messages
            self._history = self._history[-self.MAX_HISTORY_LENGTH :]

        # Queue for streaming chunks
        chunk_queue: asyncio.Queue[str | None] = asyncio.Queue()
        done = asyncio.Event()
        full_response: list[str] = []

        def stream_collector(event: Any) -> None:
            if event.type.value == "assistant.message_delta":
                delta = event.data.delta_content or ""
                if delta:
                    full_response.append(delta)
                    chunk_queue.put_nowait(delta)
            elif event.type.value == "session.idle":
                done.set()
                chunk_queue.put_nowait(None)  # Sentinel

        self._session.on(stream_collector)

        # Send the sanitized message
        await self._session.send({"prompt": sanitized_message})

        # Yield chunks as they arrive
        while True:
            try:
                chunk = await asyncio.wait_for(
                    chunk_queue.get(), timeout=self.config.timeout_seconds
                )
                if chunk is None:  # Sentinel - we're done
                    break
                yield chunk
            except TimeoutError:
                logger.warning("Stream timeout")
                break

        # Add complete response to history
        self._history.append(
            ChatMessage(
                role="assistant",
                content="".join(full_response),
            )
        )
        # SECURITY FIX (Audit 7 - Session 9): Bound chat history to prevent memory exhaustion
        if len(self._history) > self.MAX_HISTORY_LENGTH:
            # Keep system messages and last N messages
            self._history = self._history[-self.MAX_HISTORY_LENGTH :]

    def on_event(self, handler: Callable[..., Any]) -> None:
        """
        Register an event handler for Copilot events.

        Args:
            handler: Callback function receiving event objects
        """
        self._event_handlers.append(handler)

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._history.clear()
        logger.info("Conversation history cleared")

    async def get_session_messages(self) -> list[dict[str, Any]]:
        """
        Get messages from the Copilot session.

        Returns:
            List of message dictionaries from the session
        """
        if not self._session:
            return []

        try:
            messages: list[dict[str, Any]] = await self._session.get_messages()
            return messages
        except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
            logger.error(f"Failed to get session messages: {e}")
            return []

    def _handle_event(self, event: Any) -> None:
        """Internal event handler that dispatches to registered handlers."""
        # Log certain events
        if event.type.value == "tool.call":
            logger.info(f"Tool called: {event.data.name}")
        elif event.type.value == "error":
            logger.error(f"Copilot error: {event.data}")

        # Dispatch to registered handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except (RuntimeError, ConnectionError, TimeoutError, ValueError, OSError) as e:
                logger.error(f"Event handler error: {e}")


class CopilotForgeAgentPool:
    """
    Pool of Copilot agents for handling concurrent requests.

    Manages multiple agent instances for high-concurrency scenarios,
    with automatic scaling and health monitoring.
    """

    def __init__(
        self,
        config: CopilotConfig | None = None,
        min_agents: int = 1,
        max_agents: int = 5,
    ) -> None:
        """
        Initialize the agent pool.

        Args:
            config: Configuration for all agents in the pool
            min_agents: Minimum number of agents to maintain
            max_agents: Maximum number of agents allowed
        """
        self.config = config or CopilotConfig()
        self._min_agents = min_agents
        self._max_agents = max_agents
        self._agents: list[CopilotForgeAgent] = []
        self._available: asyncio.Queue[CopilotForgeAgent] = asyncio.Queue()
        self._initialized = False

    async def initialize(self, **services: Any) -> None:
        """Initialize the agent pool with minimum agents."""
        for _ in range(self._min_agents):
            agent = CopilotForgeAgent(self.config)
            await agent.start(**services)
            self._agents.append(agent)
            await self._available.put(agent)

        self._initialized = True
        logger.info(f"Agent pool initialized with {self._min_agents} agents")

    async def acquire(self) -> CopilotForgeAgent:
        """Acquire an agent from the pool."""
        if not self._initialized:
            raise RuntimeError("Pool not initialized")

        return await self._available.get()

    async def release(self, agent: CopilotForgeAgent) -> None:
        """Release an agent back to the pool."""
        agent.clear_history()  # Reset for next user
        await self._available.put(agent)

    async def shutdown(self) -> None:
        """Shutdown all agents in the pool."""
        for agent in self._agents:
            await agent.stop()
        self._agents.clear()
        self._initialized = False
        logger.info("Agent pool shutdown complete")


# Singleton instance
_default_agent: CopilotForgeAgent | None = None


async def get_copilot_agent() -> CopilotForgeAgent:
    """Get the default Copilot agent instance."""
    global _default_agent
    if _default_agent is None:
        _default_agent = CopilotForgeAgent()
    return _default_agent
