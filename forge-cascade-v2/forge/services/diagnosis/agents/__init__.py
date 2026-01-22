"""
Multi-Agent Diagnostic System

Provides specialized diagnostic agents that collaborate:
- PhenotypeAgent: Analyzes phenotypic evidence
- GeneticAgent: Evaluates genetic findings
- DifferentialAgent: Synthesizes differential diagnoses
- DiagnosticCoordinator: Orchestrates agent collaboration
"""

from .base import (
    AgentConfig,
    AgentMessage,
    AgentRole,
    DiagnosticAgent,
    MessageType,
)
from .coordinator import (
    CoordinatorConfig,
    DiagnosticCoordinator,
    create_diagnostic_coordinator,
)
from .differential_agent import (
    DifferentialAgent,
    create_differential_agent,
)
from .genetic_agent import (
    GeneticAgent,
    create_genetic_agent,
)
from .phenotype_agent import (
    PhenotypeAgent,
    create_phenotype_agent,
)

__all__ = [
    # Base
    "DiagnosticAgent",
    "AgentConfig",
    "AgentMessage",
    "AgentRole",
    "MessageType",
    # Specialist Agents
    "PhenotypeAgent",
    "create_phenotype_agent",
    "GeneticAgent",
    "create_genetic_agent",
    "DifferentialAgent",
    "create_differential_agent",
    # Coordinator
    "DiagnosticCoordinator",
    "CoordinatorConfig",
    "create_diagnostic_coordinator",
]
