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
    OverlayContext,
    OverlayResult,
    
    # Built-in overlays
    PassthroughOverlay,
    CompositeOverlay,
    
    # Exceptions
    OverlayError,
    CapabilityError,
    ResourceLimitError,
    OverlayTimeoutError,
)

from .security_validator import (
    SecurityValidatorOverlay,
    create_security_validator,
    
    # Rules
    ValidationRule,
    ContentPolicyRule,
    TrustRule,
    RateLimitRule,
    InputSanitizationRule,
    
    # Results
    ValidationResult,
    
    # Exceptions
    SecurityValidationError,
    ThreatDetectedError,
    RateLimitExceededError,
)

from .ml_intelligence import (
    MLIntelligenceOverlay,
    create_ml_intelligence,
    
    # Results
    EmbeddingResult,
    ClassificationResult,
    EntityExtractionResult,
    PatternMatch,
    AnalysisResult,
    
    # Exceptions
    MLProcessingError,
    EmbeddingError,
)

from .governance import (
    GovernanceOverlay,
    create_governance_overlay,
    
    # Configuration
    ConsensusConfig,
    PolicyRule,
    
    # Data classes
    VoteRecord,
    ConsensusResult,
    GovernanceDecision,
    VotingStatus,
    
    # Exceptions
    GovernanceError,
    InsufficientQuorumError,
    PolicyViolationError,
    ConsensusFailedError,
)

from .lineage_tracker import (
    LineageTrackerOverlay,
    create_lineage_tracker,
    
    # Data classes
    LineageNode,
    LineageChain,
    LineageMetrics,
    LineageAnomaly,
    
    # Exceptions
    LineageError,
    CircularLineageError,
    BrokenChainError,
)

from .performance_optimizer import (
    PerformanceOptimizerOverlay,
)

from .capsule_analyzer import (
    CapsuleAnalyzerOverlay,
)

from .graph_algorithms import (
    GraphAlgorithmsOverlay,
    create_graph_algorithms_overlay,
    GraphAlgorithmError,
    AlgorithmConfig,
)

from .knowledge_query import (
    KnowledgeQueryOverlay,
    create_knowledge_query_overlay,
    QueryCompilationError,
    QueryExecutionError,
    QueryConfig,
)

from .temporal_tracker import (
    TemporalTrackerOverlay,
    create_temporal_tracker_overlay,
    TemporalError,
    VersionNotFoundError,
    TemporalConfig,
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
]
