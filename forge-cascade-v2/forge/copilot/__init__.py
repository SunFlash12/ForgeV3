"""
GitHub Copilot SDK Integration for Forge

This module integrates GitHub's Copilot SDK (Technical Preview, January 2026)
to provide AI-powered agentic workflows within Forge.

The integration exposes Forge's knowledge management capabilities as custom
tools that Copilot can invoke during conversations:
- Knowledge graph queries
- Semantic search
- Capsule creation and retrieval
- Governance operations

Requirements:
- GitHub Copilot subscription
- Copilot CLI installed (`copilot` in PATH)
- pip install github-copilot-sdk

Example:
    ```python
    from forge.copilot import CopilotForgeAgent

    agent = CopilotForgeAgent()
    await agent.start()

    response = await agent.chat("Find all capsules about machine learning")
    print(response)

    await agent.stop()
    ```

References:
- https://github.com/github/copilot-sdk
- https://github.blog/changelog/2026-01-14-copilot-sdk-in-technical-preview/
"""

from .agent import CopilotConfig, CopilotForgeAgent
from .tools import (
    ForgeToolRegistry,
    create_capsule_tool,
    get_capsule_tool,
    knowledge_query_tool,
    list_overlays_tool,
    semantic_search_tool,
)

__all__ = [
    "CopilotForgeAgent",
    "CopilotConfig",
    "ForgeToolRegistry",
    "knowledge_query_tool",
    "semantic_search_tool",
    "create_capsule_tool",
    "get_capsule_tool",
    "list_overlays_tool",
]
