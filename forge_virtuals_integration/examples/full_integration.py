"""
Comprehensive Example: Forge-Virtuals Protocol Integration

This example demonstrates the complete integration workflow between Forge
and Virtuals Protocol, including:

1. Creating a knowledge agent from a Forge overlay
2. Tokenizing the agent for revenue generation
3. Setting up ACP commerce capabilities
4. Processing revenue and distributions

This serves as both a tutorial and a reference implementation for
integrating Forge with the Virtuals Protocol ecosystem.

Prerequisites:
- VIRTUALS_API_KEY environment variable set
- VIRTUALS_OPERATOR_PRIVATE_KEY environment variable set (for blockchain ops)
- Forge services running with capsule and overlay repositories

Run with: python -m examples.full_integration
"""

import asyncio
import os
from datetime import datetime, timedelta

# ============================================================================
# SECTION 1: Configuration and Initialization
# ============================================================================

async def setup_environment():
    """
    Configure the Virtuals integration environment.
    
    This demonstrates how to set up configuration either through
    environment variables or programmatic configuration. In production,
    you would typically use environment variables or a configuration
    management system.
    """
    from forge.virtuals import (
        VirtualsConfig,
        VirtualsEnvironment,
        ChainNetwork,
        configure_virtuals,
    )
    
    # Option 1: Use environment variables (recommended for production)
    # The config automatically reads from VIRTUALS_* env vars
    # export VIRTUALS_API_KEY="your-key"
    # export VIRTUALS_OPERATOR_PRIVATE_KEY="0x..."
    
    # Option 2: Programmatic configuration (useful for testing)
    config = VirtualsConfig(
        api_key=os.environ.get("VIRTUALS_API_KEY", ""),
        environment=VirtualsEnvironment.TESTNET,  # Use testnet for development
        primary_chain=ChainNetwork.BASE_SEPOLIA,   # Base testnet
        enabled_chains=[
            ChainNetwork.BASE_SEPOLIA,
            ChainNetwork.ETHEREUM_SEPOLIA,
        ],
        # Feature flags
        enable_tokenization=True,
        enable_acp=True,
        enable_cross_chain=False,  # Disable for initial testing
        enable_revenue_sharing=True,
    )
    
    configure_virtuals(config)
    print("✓ Configuration complete")
    return config


async def initialize_services():
    """
    Initialize all Virtuals Protocol services.
    
    This demonstrates the proper initialization order and shows how
    services are connected. The chain manager must be initialized first
    as other services depend on blockchain connectivity.
    """
    from forge.virtuals import initialize_virtuals
    
    print("\nInitializing Virtuals Protocol services...")
    
    services = await initialize_virtuals()
    
    print(f"  ✓ Chain manager initialized")
    print(f"  ✓ GAME client initialized")
    print(f"  ✓ Primary chain: {services['config'].primary_chain.value}")
    
    return services


# ============================================================================
# SECTION 2: Creating a Knowledge Agent
# ============================================================================

async def create_knowledge_agent(game_client):
    """
    Create an AI agent that provides knowledge services.
    
    This example creates an agent that can search and retrieve information
    from Forge knowledge capsules. The agent uses the GAME framework for
    autonomous decision-making and can be tokenized for revenue generation.
    
    The agent is configured with:
    - A personality defining how it communicates
    - Goals that drive its decision-making
    - Workers that enable specific capabilities
    """
    from forge.virtuals import (
        ForgeAgentCreate,
        AgentPersonality,
        AgentGoals,
    )
    from forge.virtuals.models import AgentMemoryConfig
    from forge.virtuals.game import (
        GAMEWorker,
        FunctionDefinition,
    )
    
    print("\n" + "="*60)
    print("CREATING KNOWLEDGE AGENT")
    print("="*60)
    
    # Step 1: Define the agent's personality
    # This shapes how the agent communicates and presents information
    personality = AgentPersonality(
        name="Forge Knowledge Oracle",
        description=(
            "An intelligent knowledge agent that helps users discover and "
            "understand information stored in Forge's institutional memory. "
            "Specializes in synthesizing complex information and providing "
            "clear, actionable insights."
        ),
        personality_traits=[
            "analytical",
            "helpful",
            "thorough",
            "patient",
        ],
        communication_style="professional",
        expertise_domains=[
            "knowledge management",
            "information synthesis",
            "enterprise data",
        ],
        response_guidelines=(
            "Always cite sources when providing information. "
            "Break down complex topics into understandable parts. "
            "Suggest related topics the user might want to explore."
        ),
    )
    print(f"  ✓ Defined personality: {personality.name}")
    
    # Step 2: Define the agent's goals
    # Goals drive the high-level planner's decision-making
    goals = AgentGoals(
        primary_goal=(
            "Help users find and understand relevant information from "
            "the Forge knowledge base efficiently and accurately."
        ),
        secondary_goals=[
            "Build trust through accurate and well-sourced responses",
            "Identify gaps in knowledge and suggest improvements",
            "Maintain user engagement through helpful suggestions",
        ],
        constraints=[
            "Never provide information without verifying its source",
            "Respect access controls on sensitive capsules",
            "Prioritize accuracy over speed",
        ],
        success_metrics=[
            "User satisfaction ratings",
            "Query resolution rate",
            "Knowledge discovery rate",
        ],
    )
    print(f"  ✓ Defined goals: {goals.primary_goal[:50]}...")
    
    # Step 3: Create custom functions for the agent
    # These define the specific actions the agent can take
    
    async def search_knowledge(query: str, limit: int = 5):
        """
        Search the knowledge base for relevant capsules.
        
        In production, this would connect to Forge's actual capsule
        repository. Here we simulate the search for demonstration.
        """
        # Simulated search results
        results = [
            {
                "id": f"capsule_{i}",
                "title": f"Result {i} for: {query}",
                "relevance": 0.9 - (i * 0.1),
            }
            for i in range(min(limit, 5))
        ]
        return "DONE", results, {"last_query": query}
    
    search_function = FunctionDefinition(
        name="search_knowledge",
        description=(
            "Search the Forge knowledge base for capsules matching a query. "
            "Use this to find relevant information before answering questions."
        ),
        arguments=[
            {
                "name": "query",
                "type": "string",
                "description": "Natural language search query",
            },
            {
                "name": "limit",
                "type": "integer",
                "description": "Maximum results to return (default: 5)",
            },
        ],
        executable=search_knowledge,
    )
    
    async def get_capsule_content(capsule_id: str):
        """Retrieve the full content of a specific capsule."""
        # Simulated capsule retrieval
        content = {
            "id": capsule_id,
            "title": f"Capsule {capsule_id}",
            "content": "This is the full content of the capsule...",
            "trust_level": 0.95,
        }
        return "DONE", content, {"retrieved_capsule": capsule_id}
    
    retrieve_function = FunctionDefinition(
        name="get_capsule_content",
        description="Retrieve the full content of a knowledge capsule by ID.",
        arguments=[
            {
                "name": "capsule_id",
                "type": "string",
                "description": "The unique identifier of the capsule",
            },
        ],
        executable=get_capsule_content,
    )
    
    # Step 4: Create a worker with these functions
    # Workers are specialized components that handle specific task types
    knowledge_worker = GAMEWorker(
        worker_id="knowledge_retrieval",
        description=(
            "Handles all knowledge retrieval operations including searching, "
            "fetching, and synthesizing information from Forge capsules."
        ),
        functions=[search_function, retrieve_function],
    )
    print(f"  ✓ Created worker: {knowledge_worker.worker_id}")
    
    # Step 5: Create the agent configuration
    create_request = ForgeAgentCreate(
        name="forge-knowledge-oracle",
        personality=personality,
        goals=goals,
        workers=[],  # Workers passed separately to create_agent
        memory_config=AgentMemoryConfig(
            enable_long_term_memory=True,
            memory_retention_days=365,
            enable_cross_platform_sync=True,
        ),
        enable_tokenization=False,  # We'll tokenize separately
        primary_chain="base",
    )
    
    # Step 6: Create the agent via GAME SDK
    print("\n  Creating agent via GAME SDK...")
    
    try:
        agent = await game_client.create_agent(
            create_request=create_request,
            workers=[knowledge_worker],
        )
        print(f"  ✓ Agent created: {agent.id}")
        print(f"    GAME ID: {agent.game_agent_id}")
        print(f"    Status: {agent.status.value}")
        
        return agent, {"knowledge_retrieval": knowledge_worker}
        
    except Exception as e:
        print(f"  ✗ Agent creation failed: {e}")
        print("    (This is expected without a valid API key)")
        # Return a mock agent for demonstration
        return None, {"knowledge_retrieval": knowledge_worker}


# ============================================================================
# SECTION 3: Running the Agent
# ============================================================================

async def demonstrate_agent_execution(game_client, agent, workers):
    """
    Demonstrate the agent's autonomous decision-making loop.
    
    This shows how the GAME framework enables agents to:
    1. Receive a context/query from a user
    2. Plan appropriate actions using the high-level planner
    3. Execute actions through workers
    4. Return results to the user
    
    The agent runs autonomously, deciding which functions to call
    and in what order based on the context and its goals.
    """
    print("\n" + "="*60)
    print("RUNNING AGENT DECISION LOOP")
    print("="*60)
    
    if agent is None:
        print("\n  Simulating agent execution (no real agent created)")
        
        # Demonstrate what would happen
        context = "What do we know about our Q3 marketing strategy?"
        print(f"\n  User query: {context}")
        
        print("\n  Agent would execute:")
        print("    1. Call search_knowledge('Q3 marketing strategy')")
        print("    2. Review search results")
        print("    3. Call get_capsule_content() for relevant capsules")
        print("    4. Synthesize information")
        print("    5. Return comprehensive response")
        
        return
    
    # Real agent execution
    context = "What do we know about our Q3 marketing strategy?"
    print(f"\n  User query: {context}")
    
    results = await game_client.run_agent_loop(
        agent=agent,
        workers=workers,
        context=context,
        max_iterations=5,
    )
    
    print(f"\n  Agent completed {len(results)} actions:")
    for i, result in enumerate(results):
        print(f"    {i+1}. {result['worker_id']}.{result['function_name']}")
        print(f"       Status: {result['status']}")
        if result.get('reasoning'):
            print(f"       Reasoning: {result['reasoning'][:100]}...")


# ============================================================================
# SECTION 4: Tokenizing the Agent
# ============================================================================

async def tokenize_agent(agent):
    """
    Tokenize the agent for revenue generation.
    
    This demonstrates the opt-in tokenization process:
    1. Create a tokenization request with configuration
    2. Submit initial VIRTUAL stake
    3. Monitor bonding curve progress
    4. (Eventually) graduate to full token status
    
    Tokenization enables:
    - Revenue from agent usage (inference fees)
    - Token holder governance
    - Cross-chain deployment
    - Tradeable ownership shares
    """
    from forge.virtuals import (
        TokenizationRequest,
        TokenDistribution,
        RevenueShare,
    )
    
    print("\n" + "="*60)
    print("TOKENIZING AGENT")
    print("="*60)
    
    # Configure tokenization
    request = TokenizationRequest(
        entity_type="agent",
        entity_id=agent.id if agent else "demo_agent_123",
        token_name="Forge Knowledge Oracle Token",
        token_symbol="FKOT",
        token_description=(
            "Token representing ownership in the Forge Knowledge Oracle agent. "
            "Holders receive governance rights and share in query revenue."
        ),
        launch_type="standard",  # Standard bonding curve
        initial_stake_virtual=100.0,  # Minimum required stake
        distribution=TokenDistribution(
            public_circulation_percent=60.0,
            ecosystem_treasury_percent=35.0,
            liquidity_pool_percent=5.0,
        ),
        revenue_share=RevenueShare(
            creator_share_percent=30.0,
            contributor_share_percent=20.0,
            treasury_share_percent=50.0,
            buyback_burn_percent=50.0,  # Half of treasury goes to buyback-burn
        ),
        enable_holder_governance=True,
        governance_quorum_percent=10.0,
        primary_chain="base",
        enable_multichain=False,  # Start single-chain
        owner_wallet="0x0000000000000000000000000000000000000000",
    )
    
    print(f"  Token Name: {request.token_name}")
    print(f"  Symbol: {request.token_symbol}")
    print(f"  Initial Stake: {request.initial_stake_virtual} VIRTUAL")
    print(f"  Launch Type: {request.launch_type}")
    
    # In production, this would call the tokenization service:
    # service = await get_tokenization_service(entity_repo, contrib_repo, proposal_repo)
    # entity = await service.request_tokenization(request)
    
    print("\n  Tokenization would:")
    print("    1. Deploy ERC-20 token contract in bonding curve phase")
    print("    2. Create ERC-6551 token-bound wallet")
    print("    3. Lock initial stake in bonding curve")
    print("    4. Issue FERC20 placeholder tokens to creator")
    print(f"    5. Progress toward graduation (0% → 100% at 42,000 VIRTUAL)")
    
    # Simulated tokenized entity
    print(f"\n  ✓ Token created (simulated)")
    print(f"    Bonding curve progress: 0.24%")
    print(f"    Estimated graduation: ~42 days")
    
    return request


# ============================================================================
# SECTION 5: Setting Up ACP Commerce
# ============================================================================

async def setup_acp_commerce(agent):
    """
    Set up Agent Commerce Protocol capabilities.
    
    This enables the agent to participate in agent-to-agent commerce:
    - Offering services to other agents
    - Purchasing services from specialized agents
    - Secure transactions with escrow
    
    ACP is crucial for multi-agent coordination where specialized
    agents collaborate on complex tasks.
    """
    from forge.virtuals.models import JobOffering
    
    print("\n" + "="*60)
    print("SETTING UP ACP COMMERCE")
    print("="*60)
    
    # Create a service offering
    # This advertises the agent's capabilities to others
    offering = JobOffering(
        provider_agent_id=agent.id if agent else "demo_agent_123",
        provider_wallet="0x0000000000000000000000000000000000000000",
        service_type="knowledge_query",
        title="Enterprise Knowledge Search",
        description=(
            "Search and synthesize information from Forge's institutional "
            "knowledge base. Includes semantic search, content retrieval, "
            "and intelligent summarization."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
                "capsule_types": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["query"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "results": {"type": "array"},
                "summary": {"type": "string"},
            },
        },
        base_fee_virtual=0.1,  # 0.1 VIRTUAL per query
        fee_per_unit=0.001,    # Plus 0.001 per 1000 tokens
        unit_type="tokens",
        max_execution_time_seconds=60,
        requires_escrow=True,
        min_buyer_trust_score=0.3,
        tags=["knowledge", "search", "enterprise", "ai"],
    )
    
    print(f"  Service: {offering.title}")
    print(f"  Type: {offering.service_type}")
    print(f"  Base Fee: {offering.base_fee_virtual} VIRTUAL")
    print(f"  Requires Escrow: {offering.requires_escrow}")
    
    # In production, this would register with ACP:
    # service = await get_acp_service(job_repo, offering_repo)
    # registered = await service.register_offering(agent_id, wallet, offering)
    
    print("\n  ACP registration would:")
    print("    1. Store offering in local registry")
    print("    2. Register on-chain for discoverability")
    print("    3. Enable other agents to create jobs")
    
    # Demonstrate a typical ACP transaction flow
    print("\n  Example ACP Transaction Flow:")
    print("    REQUEST: Buyer agent discovers offering, creates job")
    print("    NEGOTIATION: Provider responds with specific terms")
    print("    TRANSACTION: Buyer accepts, funds escrowed, work begins")
    print("    EVALUATION: Deliverable reviewed, funds released")
    
    return offering


# ============================================================================
# SECTION 6: Revenue Tracking
# ============================================================================

async def demonstrate_revenue():
    """
    Demonstrate revenue tracking and distribution.
    
    This shows how the system tracks various revenue streams:
    - Inference fees from knowledge queries
    - Service fees from overlay usage
    - Governance rewards for participation
    - Trading fees (Sentient Tax)
    
    Revenue is automatically distributed according to the entity's
    RevenueShare configuration.
    """
    from forge.virtuals.models import RevenueType
    
    print("\n" + "="*60)
    print("REVENUE TRACKING")
    print("="*60)
    
    # Simulate various revenue events
    revenue_events = [
        {
            "type": RevenueType.INFERENCE_FEE,
            "amount": 0.1,
            "source": "Knowledge query from user",
        },
        {
            "type": RevenueType.SERVICE_FEE,
            "amount": 0.5,
            "source": "ACP job completion",
        },
        {
            "type": RevenueType.GOVERNANCE_REWARD,
            "amount": 0.01,
            "source": "Governance vote participation",
        },
    ]
    
    total_revenue = sum(e["amount"] for e in revenue_events)
    
    print("\n  Revenue Events:")
    for event in revenue_events:
        print(f"    • {event['type'].value}: {event['amount']} VIRTUAL")
        print(f"      Source: {event['source']}")
    
    print(f"\n  Total Revenue: {total_revenue} VIRTUAL")
    
    # Show distribution based on typical RevenueShare
    print("\n  Distribution (based on default RevenueShare):")
    creator_share = total_revenue * 0.30
    contributor_share = total_revenue * 0.20
    treasury_share = total_revenue * 0.50
    buyback_amount = treasury_share * 0.50
    
    print(f"    • Creator: {creator_share:.4f} VIRTUAL (30%)")
    print(f"    • Contributors: {contributor_share:.4f} VIRTUAL (20%)")
    print(f"    • Treasury: {treasury_share - buyback_amount:.4f} VIRTUAL (25%)")
    print(f"    • Buyback-Burn: {buyback_amount:.4f} VIRTUAL (25%)")
    
    # In production:
    # service = await get_revenue_service(revenue_repo)
    # await service.record_inference_fee(capsule_id, wallet, query, tokens)
    # summary = await service.get_revenue_summary()


# ============================================================================
# SECTION 7: Main Execution
# ============================================================================

async def main():
    """
    Main execution function demonstrating the complete integration.
    
    This runs through all the major features of the Forge-Virtuals
    integration in a logical order, showing how they connect.
    """
    print("\n" + "="*60)
    print("FORGE-VIRTUALS PROTOCOL INTEGRATION DEMO")
    print("="*60)
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    
    # Step 1: Setup
    config = await setup_environment()
    services = await initialize_services()
    
    # Step 2: Create agent
    agent, workers = await create_knowledge_agent(services['game'])
    
    # Step 3: Run agent
    await demonstrate_agent_execution(services['game'], agent, workers)
    
    # Step 4: Tokenize
    token_request = await tokenize_agent(agent)
    
    # Step 5: Setup ACP
    offering = await setup_acp_commerce(agent)
    
    # Step 6: Revenue
    await demonstrate_revenue()
    
    # Summary
    print("\n" + "="*60)
    print("INTEGRATION COMPLETE")
    print("="*60)
    print("\n  This demonstration showed:")
    print("    1. Configuration and service initialization")
    print("    2. Creating a GAME-powered knowledge agent")
    print("    3. Running the agent's autonomous decision loop")
    print("    4. Opt-in tokenization with bonding curve")
    print("    5. ACP commerce setup for agent-to-agent transactions")
    print("    6. Revenue tracking and distribution")
    print("\n  For production deployment:")
    print("    • Set valid VIRTUALS_API_KEY")
    print("    • Configure blockchain wallets")
    print("    • Connect Forge repositories")
    print("    • Enable desired feature flags")
    print("\n  Documentation: docs/virtuals-integration.md")


if __name__ == "__main__":
    asyncio.run(main())
