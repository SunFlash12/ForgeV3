"""
Forge Cascade V2 Overlays

Core overlay implementations for the 7-phase pipeline.

Overlays are self-contained processors that handle specific aspects
of capsule and event processing. Each overlay subscribes to relevant
events and performs its specialized function.

Pipeline Phase Mapping:
- INGESTION: (Built-in) Data validation and normalization
- ANALYSIS: MLIntelligenceOverlay - Pattern recognition, classification, embeddings
- VALIDATION: SecurityValidatorOverlay - Security checks, trust verification
- CONSENSUS: GovernanceOverlay - Voting, proposals, policy enforcement
- EXECUTION: (Built-in) Core processing and state changes
- PROPAGATION: (Built-in) Cascade effects, event emission
- SETTLEMENT: LineageTrackerOverlay - Ancestry tracking, Isnad chains
"""

from .base import (
    # Base classes
    BaseOverlay,
    CapabilityError,
    CompositeOverlay,
    OverlayContext,
    # Exceptions
    OverlayError,
    OverlayResult,
    OverlayTimeoutError,
    # Built-in overlays
    PassthroughOverlay,
    ResourceLimitError,
)
from .capsule_analyzer import (
    CapsuleAnalyzerOverlay,
)
from .governance import (
    # Configuration
    ConsensusConfig,
    ConsensusFailedError,
    ConsensusResult,
    GovernanceDecision,
    # Exceptions
    GovernanceError,
    GovernanceOverlay,
    InsufficientQuorumError,
    PolicyRule,
    PolicyViolationError,
    # Data classes
    VoteRecord,
    VotingStatus,
    create_governance_overlay,
)
from .graph_algorithms import (
    AlgorithmConfig,
    GraphAlgorithmError,
    GraphAlgorithmsOverlay,
    create_graph_algorithms_overlay,
)
from .knowledge_query import (
    KnowledgeQueryOverlay,
    QueryCompilationError,
    QueryConfig,
    QueryExecutionError,
    create_knowledge_query_overlay,
)
from .lineage_tracker import (
    BrokenChainError,
    CircularLineageError,
    LineageAnomaly,
    LineageChain,
    # Exceptions
    LineageError,
    LineageMetrics,
    # Data classes
    LineageNode,
    LineageTrackerOverlay,
    create_lineage_tracker,
)
from .ml_intelligence import (
    AnalysisResult,
    ClassificationResult,
    EmbeddingError,
    # Results
    EmbeddingResult,
    EntityExtractionResult,
    MLIntelligenceOverlay,
    # Exceptions
    MLProcessingError,
    PatternMatch,
    create_ml_intelligence,
)
from .performance_optimizer import (
    PerformanceOptimizerOverlay,
)
from .primekg_overlay import (
    PrimeKGError,
    PrimeKGOverlay,
    create_primekg_overlay,
)
from .security_validator import (
    ContentPolicyRule,
    InputSanitizationRule,
    RateLimitExceededError,
    RateLimitRule,
    # Exceptions
    SecurityValidationError,
    SecurityValidatorOverlay,
    ThreatDetectedError,
    TrustRule,
    # Results
    ValidationResult,
    # Rules
    ValidationRule,
    create_security_validator,
)
from .temporal_tracker import (
    TemporalConfig,
    TemporalError,
    TemporalTrackerOverlay,
    VersionNotFoundError,
    create_temporal_tracker_overlay,
)

__all__ = [
    # Base
    "BaseOverlay",
    "OverlayContext",
    "OverlayResult",
    "PassthroughOverlay",
    "CompositeOverlay",
    "OverlayError",
    "CapabilityError",
    "ResourceLimitError",
    "OverlayTimeoutError",
    # Security Validator
    "SecurityValidatorOverlay",
    "create_security_validator",
    "ValidationRule",
    "ContentPolicyRule",
    "TrustRule",
    "RateLimitRule",
    "InputSanitizationRule",
    "ValidationResult",
    "SecurityValidationError",
    "ThreatDetectedError",
    "RateLimitExceededError",
    # ML Intelligence
    "MLIntelligenceOverlay",
    "create_ml_intelligence",
    "EmbeddingResult",
    "ClassificationResult",
    "EntityExtractionResult",
    "PatternMatch",
    "AnalysisResult",
    "MLProcessingError",
    "EmbeddingError",
    # Governance
    "GovernanceOverlay",
    "create_governance_overlay",
    "ConsensusConfig",
    "PolicyRule",
    "VoteRecord",
    "ConsensusResult",
    "GovernanceDecision",
    "VotingStatus",
    "GovernanceError",
    "InsufficientQuorumError",
    "PolicyViolationError",
    "ConsensusFailedError",
    # Lineage Tracker
    "LineageTrackerOverlay",
    "create_lineage_tracker",
    "LineageNode",
    "LineageChain",
    "LineageMetrics",
    "LineageAnomaly",
    "LineageError",
    "CircularLineageError",
    "BrokenChainError",
    # Performance Optimizer
    "PerformanceOptimizerOverlay",
    # Capsule Analyzer
    "CapsuleAnalyzerOverlay",
    # Graph Algorithms
    "GraphAlgorithmsOverlay",
    "create_graph_algorithms_overlay",
    "GraphAlgorithmError",
    "AlgorithmConfig",
    # Knowledge Query
    "KnowledgeQueryOverlay",
    "create_knowledge_query_overlay",
    "QueryCompilationError",
    "QueryExecutionError",
    "QueryConfig",
    # Temporal Tracker
    "TemporalTrackerOverlay",
    "create_temporal_tracker_overlay",
    "TemporalError",
    "VersionNotFoundError",
    "TemporalConfig",
    # PrimeKG Biomedical Knowledge Graph
    "PrimeKGOverlay",
    "create_primekg_overlay",
    "PrimeKGError",
]
