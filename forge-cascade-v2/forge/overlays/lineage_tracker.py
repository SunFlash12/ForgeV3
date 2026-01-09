"""
Lineage Tracker Overlay for Forge Cascade V2

Tracks capsule ancestry (Isnad), provenance, and relationships.
Part of the SETTLEMENT phase in the 7-phase pipeline.

Responsibilities:
- Track capsule derivation chains (parent → child)
- Maintain Isnad (chain of transmission)
- Compute lineage metrics
- Detect lineage anomalies
- Generate lineage visualizations
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from collections import defaultdict
import structlog

from ..models.events import Event, EventType
from ..models.overlay import Capability
from ..models.capsule import CapsuleType
from .base import (
    BaseOverlay,
    OverlayContext,
    OverlayResult,
    OverlayError
)

logger = structlog.get_logger()


class LineageError(OverlayError):
    """Lineage tracking error."""
    pass


class CircularLineageError(LineageError):
    """Circular reference detected in lineage."""
    pass


class BrokenChainError(LineageError):
    """Lineage chain is broken."""
    pass


@dataclass
class SemanticEdgeInfo:
    """Information about a semantic edge."""
    target_id: str
    relationship_type: str  # SUPPORTS, CONTRADICTS, etc.
    confidence: float = 1.0
    bidirectional: bool = False


@dataclass
class LineageNode:
    """A node in the lineage graph."""
    capsule_id: str
    capsule_type: str
    title: Optional[str] = None
    creator_id: Optional[str] = None
    created_at: Optional[datetime] = None
    trust_at_creation: int = 60

    # Derivation relationships (DERIVED_FROM)
    parent_ids: list[str] = field(default_factory=list)
    child_ids: list[str] = field(default_factory=list)

    # Semantic relationships
    semantic_edges: list[SemanticEdgeInfo] = field(default_factory=list)
    supports: list[str] = field(default_factory=list)  # IDs this capsule supports
    supported_by: list[str] = field(default_factory=list)  # IDs that support this capsule
    contradicts: list[str] = field(default_factory=list)  # IDs this capsule contradicts
    elaborates: list[str] = field(default_factory=list)  # IDs this capsule elaborates
    references: list[str] = field(default_factory=list)  # IDs this capsule references
    related_to: list[str] = field(default_factory=list)  # Generic semantic relations

    # Metrics
    depth: int = 0  # Distance from root (derivation)
    descendant_count: int = 0
    influence_score: float = 0.0
    semantic_connectivity: int = 0  # Total semantic edges


@dataclass
class LineageChain:
    """A chain of lineage (Isnad)."""
    chain_id: str
    root_id: str
    leaf_id: str
    nodes: list[str]  # Ordered from root to leaf
    total_length: int = 0
    trust_gradient: list[int] = field(default_factory=list)  # Trust at each level
    
    @property
    def is_valid(self) -> bool:
        """Check if chain is valid (no gaps)."""
        return len(self.nodes) == self.total_length and len(self.nodes) >= 1


@dataclass
class LineageMetrics:
    """Metrics for a lineage tree."""
    root_id: str
    total_nodes: int = 0
    max_depth: int = 0
    avg_depth: float = 0.0
    branching_factor: float = 0.0  # Avg children per node
    trust_decay: float = 0.0  # How trust decreases with depth
    
    # Distribution
    nodes_by_depth: dict[int, int] = field(default_factory=dict)
    nodes_by_type: dict[str, int] = field(default_factory=dict)
    nodes_by_creator: dict[str, int] = field(default_factory=dict)


@dataclass
class LineageAnomaly:
    """An anomaly detected in lineage."""
    anomaly_type: str  # "circular", "broken", "trust_spike", "rapid_derivation"
    severity: str  # "low", "medium", "high"
    affected_nodes: list[str]
    description: str
    detected_at: datetime = field(default_factory=datetime.utcnow)


class LineageTrackerOverlay(BaseOverlay):
    """
    Lineage tracking overlay for capsule ancestry.
    
    Implements the Isnad (chain of transmission) concept,
    tracking how knowledge flows and transforms through
    derivation relationships.
    """
    
    NAME = "lineage_tracker"
    VERSION = "1.0.0"
    DESCRIPTION = "Tracks capsule ancestry, provenance, and Isnad chains"
    
    SUBSCRIBED_EVENTS = {
        EventType.CAPSULE_CREATED,
        EventType.CAPSULE_UPDATED,
        EventType.CAPSULE_LINKED,
        EventType.CASCADE_TRIGGERED,
        EventType.SEMANTIC_EDGE_CREATED,  # New: track semantic relationships
    }
    
    REQUIRED_CAPABILITIES = {
        Capability.DATABASE_READ,
        Capability.DATABASE_WRITE
    }
    
    # Maximum lineage depth to track
    MAX_DEPTH = 100
    
    def __init__(
        self,
        enable_anomaly_detection: bool = True,
        enable_metrics: bool = True,
        trust_decay_rate: float = 0.05,
        max_derivations_per_day: int = 100,
        lineage_provider: Optional[Any] = None
    ):
        """
        Initialize the lineage tracker.
        
        Args:
            enable_anomaly_detection: Enable lineage anomaly detection
            enable_metrics: Enable metrics computation
            trust_decay_rate: Rate at which trust decays per derivation
            max_derivations_per_day: Alert threshold for rapid derivation
            lineage_provider: External data provider (repository)
        """
        super().__init__()
        
        self._enable_anomaly_detection = enable_anomaly_detection
        self._enable_metrics = enable_metrics
        self._trust_decay_rate = trust_decay_rate
        self._max_derivations_per_day = max_derivations_per_day
        self._lineage_provider = lineage_provider
        
        # In-memory lineage cache
        self._nodes: dict[str, LineageNode] = {}
        self._roots: set[str] = set()  # Nodes with no parents
        
        # Recent derivations for anomaly detection
        self._recent_derivations: dict[str, list[datetime]] = defaultdict(list)
        
        # Statistics
        self._stats = {
            "nodes_tracked": 0,
            "chains_computed": 0,
            "anomalies_detected": 0,
            "derivations_recorded": 0
        }
        
        self._logger = logger.bind(overlay=self.NAME)
    
    async def initialize(self) -> bool:
        """Initialize the lineage tracker."""
        self._logger.info(
            "lineage_tracker_initialized",
            anomaly_detection=self._enable_anomaly_detection,
            trust_decay_rate=self._trust_decay_rate
        )
        return True
    
    async def execute(
        self,
        context: OverlayContext,
        event: Optional[Event] = None,
        input_data: Optional[dict[str, Any]] = None
    ) -> OverlayResult:
        """
        Execute lineage tracking.
        
        Args:
            context: Execution context
            event: Triggering event
            input_data: Data to process
            
        Returns:
            Lineage tracking result
        """
        import time
        start_time = time.time()
        
        data = input_data or {}
        if event:
            data.update(event.payload or {})
            data["event_type"] = event.event_type
        
        # Determine action
        anomalies = []
        result_data = {}
        
        if event:
            if event.event_type == EventType.CAPSULE_CREATED:
                result_data = await self._handle_capsule_created(data, context)
            elif event.event_type == EventType.CAPSULE_LINKED:
                result_data = await self._handle_capsule_linked(data, context)
            elif event.event_type == EventType.CASCADE_TRIGGERED:
                result_data = await self._handle_cascade(data, context)
            elif event.event_type == EventType.SEMANTIC_EDGE_CREATED:
                result_data = await self._handle_semantic_edge_created(data, context)
            else:
                result_data = await self._get_lineage_info(data, context)
        else:
            # Direct call - get lineage info
            result_data = await self._get_lineage_info(data, context)
        
        # Check for anomalies
        if self._enable_anomaly_detection:
            capsule_id = data.get("capsule_id")
            if capsule_id:
                anomalies = self._detect_anomalies(capsule_id)
                if anomalies:
                    self._stats["anomalies_detected"] += len(anomalies)
        
        duration_ms = (time.time() - start_time) * 1000
        
        self._logger.info(
            "lineage_tracking_complete",
            nodes=len(self._nodes),
            anomalies=len(anomalies),
            duration_ms=round(duration_ms, 2)
        )
        
        # Prepare events
        events_to_emit = []
        if anomalies:
            for anomaly in anomalies:
                if anomaly.severity in {"medium", "high"}:
                    events_to_emit.append({
                        "event_type": EventType.ANOMALY_DETECTED,
                        "payload": {
                            "anomaly_type": anomaly.anomaly_type,
                            "severity": anomaly.severity,
                            "affected_nodes": anomaly.affected_nodes,
                            "description": anomaly.description
                        }
                    })
        
        return OverlayResult(
            overlay_id=self.id,
            overlay_name=self.NAME,
            success=True,
            data={
                **result_data,
                "anomalies": [
                    {
                        "type": a.anomaly_type,
                        "severity": a.severity,
                        "description": a.description
                    }
                    for a in anomalies
                ],
                "processing_time_ms": round(duration_ms, 2)
            },
            events_to_emit=events_to_emit,
            metrics={
                "nodes_tracked": len(self._nodes),
                "roots_count": len(self._roots),
                "anomalies_found": len(anomalies)
            }
        )
    
    async def _handle_capsule_created(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle new capsule creation."""
        capsule_id = data.get("capsule_id")
        parent_id = data.get("parent_id")
        parent_ids = [parent_id] if parent_id else []
        capsule_type = data.get("type", data.get("capsule_type", CapsuleType.NOTE.value))
        
        if not capsule_id:
            return {"error": "Missing capsule_id"}
        
        # Create lineage node
        node = LineageNode(
            capsule_id=capsule_id,
            capsule_type=capsule_type,
            title=data.get("title"),
            creator_id=context.user_id,
            created_at=datetime.utcnow(),
            trust_at_creation=context.trust_flame,
            parent_ids=parent_ids
        )
        
        # Calculate depth
        if parent_ids:
            parent_depths = [
                self._nodes[pid].depth 
                for pid in parent_ids 
                if pid in self._nodes
            ]
            node.depth = max(parent_depths, default=0) + 1
        else:
            # Root node
            self._roots.add(capsule_id)
        
        # Store node
        self._nodes[capsule_id] = node
        self._stats["nodes_tracked"] += 1
        
        # Update parent relationships
        for parent_id in parent_ids:
            if parent_id in self._nodes:
                self._nodes[parent_id].child_ids.append(capsule_id)
                self._update_influence(parent_id)
        
        # Track derivation for anomaly detection
        if context.user_id:
            self._recent_derivations[context.user_id].append(datetime.utcnow())
        
        self._stats["derivations_recorded"] += 1
        
        # Compute chain to root
        chain = self._compute_chain_to_root(capsule_id)
        
        return {
            "capsule_id": capsule_id,
            "depth": node.depth,
            "parent_count": len(parent_ids),
            "is_root": capsule_id in self._roots,
            "chain": {
                "root_id": chain.root_id,
                "length": chain.total_length,
                "nodes": chain.nodes
            } if chain else None
        }
    
    async def _handle_capsule_linked(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle capsule linking (new parent-child relationship)."""
        parent_id = data.get("parent_id")
        child_id = data.get("child_id")
        
        if not parent_id or not child_id:
            return {"error": "Missing parent_id or child_id"}
        
        # Check for circular reference
        if self._would_create_cycle(parent_id, child_id):
            return {
                "error": "Would create circular reference",
                "parent_id": parent_id,
                "child_id": child_id
            }
        
        # Update relationships
        if parent_id in self._nodes:
            if child_id not in self._nodes[parent_id].child_ids:
                self._nodes[parent_id].child_ids.append(child_id)
        
        if child_id in self._nodes:
            if parent_id not in self._nodes[child_id].parent_ids:
                self._nodes[child_id].parent_ids.append(parent_id)
                # Remove from roots if it was there
                self._roots.discard(child_id)
                # Recalculate depth
                self._recalculate_depth(child_id)
        
        # Update influence
        self._update_influence(parent_id)
        
        return {
            "linked": True,
            "parent_id": parent_id,
            "child_id": child_id
        }
    
    async def _handle_cascade(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle cascade event - update affected lineages."""
        source_id = data.get("source_id")
        affected_ids = data.get("affected_ids", [])

        # Update influence scores for affected nodes
        for node_id in affected_ids:
            if node_id in self._nodes:
                self._update_influence(node_id)

        # Compute metrics if enabled
        metrics = None
        if self._enable_metrics and source_id:
            metrics = self._compute_subtree_metrics(source_id)

        return {
            "cascade_processed": True,
            "source_id": source_id,
            "affected_count": len(affected_ids),
            "metrics": metrics.__dict__ if metrics else None
        }

    async def _handle_semantic_edge_created(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Handle semantic edge creation event."""
        source_id = data.get("source_id")
        target_id = data.get("target_id")
        relationship_type = data.get("relationship_type", "RELATED_TO")
        confidence = data.get("confidence", 1.0)
        bidirectional = data.get("bidirectional", False)

        if not source_id or not target_id:
            return {"error": "Missing source_id or target_id"}

        # Create edge info
        edge_info = SemanticEdgeInfo(
            target_id=target_id,
            relationship_type=relationship_type,
            confidence=confidence,
            bidirectional=bidirectional,
        )

        # Update source node
        if source_id in self._nodes:
            source_node = self._nodes[source_id]
            source_node.semantic_edges.append(edge_info)
            source_node.semantic_connectivity += 1

            # Update typed lists
            if relationship_type == "SUPPORTS":
                source_node.supports.append(target_id)
            elif relationship_type == "CONTRADICTS":
                source_node.contradicts.append(target_id)
            elif relationship_type == "ELABORATES":
                source_node.elaborates.append(target_id)
            elif relationship_type == "REFERENCES":
                source_node.references.append(target_id)
            else:
                source_node.related_to.append(target_id)

        # For bidirectional edges, also update target node
        if bidirectional and target_id in self._nodes:
            target_node = self._nodes[target_id]
            reverse_edge = SemanticEdgeInfo(
                target_id=source_id,
                relationship_type=relationship_type,
                confidence=confidence,
                bidirectional=True,
            )
            target_node.semantic_edges.append(reverse_edge)
            target_node.semantic_connectivity += 1

            if relationship_type == "SUPPORTS":
                target_node.supported_by.append(source_id)
            elif relationship_type == "CONTRADICTS":
                target_node.contradicts.append(source_id)

        # Update supported_by for target if SUPPORTS relationship
        if relationship_type == "SUPPORTS" and target_id in self._nodes:
            self._nodes[target_id].supported_by.append(source_id)

        self._logger.info(
            "semantic_edge_tracked",
            source_id=source_id,
            target_id=target_id,
            relationship_type=relationship_type,
        )

        return {
            "edge_tracked": True,
            "source_id": source_id,
            "target_id": target_id,
            "relationship_type": relationship_type,
            "bidirectional": bidirectional,
        }

    def compute_semantic_distance(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 5
    ) -> Optional[dict]:
        """
        Compute semantic distance between two capsules.

        Returns the shortest path through semantic relationships
        and the relationship types traversed.

        Args:
            source_id: Starting capsule ID
            target_id: Target capsule ID
            max_hops: Maximum path length

        Returns:
            Dict with distance, path, and relationship types, or None if not connected
        """
        if source_id not in self._nodes or target_id not in self._nodes:
            return None

        # BFS to find shortest path
        from collections import deque

        queue = deque([(source_id, [source_id], [])])
        visited = {source_id}

        while queue:
            current_id, path, rel_types = queue.popleft()

            if current_id == target_id:
                return {
                    "distance": len(path) - 1,
                    "path": path,
                    "relationship_types": rel_types,
                    "found": True,
                }

            if len(path) > max_hops:
                continue

            node = self._nodes.get(current_id)
            if not node:
                continue

            # Follow semantic edges
            for edge in node.semantic_edges:
                neighbor_id = edge.target_id
                if neighbor_id not in visited and neighbor_id in self._nodes:
                    visited.add(neighbor_id)
                    queue.append((
                        neighbor_id,
                        path + [neighbor_id],
                        rel_types + [edge.relationship_type]
                    ))

            # Also follow derivation edges
            for parent_id in node.parent_ids:
                if parent_id not in visited and parent_id in self._nodes:
                    visited.add(parent_id)
                    queue.append((
                        parent_id,
                        path + [parent_id],
                        rel_types + ["DERIVED_FROM"]
                    ))

            for child_id in node.child_ids:
                if child_id not in visited and child_id in self._nodes:
                    visited.add(child_id)
                    queue.append((
                        child_id,
                        path + [child_id],
                        rel_types + ["DERIVED_TO"]
                    ))

        return {"distance": -1, "path": [], "relationship_types": [], "found": False}

    def find_contradiction_clusters(self, min_size: int = 2) -> list[dict]:
        """
        Find clusters of mutually contradicting capsules.

        Args:
            min_size: Minimum cluster size

        Returns:
            List of contradiction clusters with their members
        """
        clusters = []
        visited = set()

        for node_id, node in self._nodes.items():
            if node_id in visited or not node.contradicts:
                continue

            # BFS to find all connected contradicting nodes
            cluster = set()
            queue = [node_id]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue

                visited.add(current)
                cluster.add(current)

                current_node = self._nodes.get(current)
                if current_node:
                    for contra_id in current_node.contradicts:
                        if contra_id not in visited and contra_id in self._nodes:
                            queue.append(contra_id)

            if len(cluster) >= min_size:
                clusters.append({
                    "cluster_id": f"contra_{len(clusters)}",
                    "capsule_ids": list(cluster),
                    "size": len(cluster),
                    "severity": "high" if len(cluster) > 3 else "medium",
                })

        return clusters
    
    async def _get_lineage_info(
        self,
        data: dict,
        context: OverlayContext
    ) -> dict:
        """Get lineage information for a capsule."""
        capsule_id = data.get("capsule_id")
        
        if not capsule_id:
            # Return overall lineage stats
            return {
                "total_nodes": len(self._nodes),
                "root_count": len(self._roots),
                "stats": self._stats
            }
        
        if capsule_id not in self._nodes:
            return {
                "capsule_id": capsule_id,
                "found": False
            }
        
        node = self._nodes[capsule_id]
        
        # Get ancestors
        ancestors = self._get_ancestors(capsule_id)
        
        # Get descendants
        descendants = self._get_descendants(capsule_id)
        
        # Compute chain to root
        chain = self._compute_chain_to_root(capsule_id)
        self._stats["chains_computed"] += 1
        
        # Compute metrics if enabled
        metrics = None
        if self._enable_metrics:
            metrics = self._compute_subtree_metrics(capsule_id)
        
        return {
            "capsule_id": capsule_id,
            "found": True,
            "node": {
                "type": node.capsule_type,
                "title": node.title,
                "creator_id": node.creator_id,
                "depth": node.depth,
                "trust_at_creation": node.trust_at_creation,
                "influence_score": round(node.influence_score, 3),
                "parent_count": len(node.parent_ids),
                "child_count": len(node.child_ids),
                "semantic_connectivity": node.semantic_connectivity,
            },
            "ancestors": {
                "count": len(ancestors),
                "ids": ancestors[:10]  # Limit for response size
            },
            "descendants": {
                "count": len(descendants),
                "ids": descendants[:10]
            },
            "isnad": {
                "chain_id": chain.chain_id if chain else None,
                "root_id": chain.root_id if chain else None,
                "length": chain.total_length if chain else 0,
                "trust_gradient": chain.trust_gradient if chain else []
            },
            "semantic_edges": {
                "supports": node.supports[:10],
                "supported_by": node.supported_by[:10],
                "contradicts": node.contradicts[:10],
                "elaborates": node.elaborates[:10],
                "references": node.references[:10],
                "related_to": node.related_to[:10],
                "total_count": node.semantic_connectivity,
            },
            "metrics": metrics.__dict__ if metrics else None
        }
    
    def _compute_chain_to_root(self, capsule_id: str) -> Optional[LineageChain]:
        """Compute the Isnad chain from capsule to root."""
        if capsule_id not in self._nodes:
            return None
        
        chain_nodes = [capsule_id]
        trust_gradient = [self._nodes[capsule_id].trust_at_creation]
        current = capsule_id
        visited = {capsule_id}
        
        while True:
            node = self._nodes.get(current)
            if not node or not node.parent_ids:
                break
            
            # Follow primary parent (first one)
            parent_id = node.parent_ids[0]
            if parent_id in visited or parent_id not in self._nodes:
                break
            
            visited.add(parent_id)
            chain_nodes.append(parent_id)
            trust_gradient.append(self._nodes[parent_id].trust_at_creation)
            current = parent_id
            
            if len(chain_nodes) >= self.MAX_DEPTH:
                break
        
        # Reverse to go from root to leaf
        chain_nodes.reverse()
        trust_gradient.reverse()
        
        return LineageChain(
            chain_id=f"chain_{capsule_id}",
            root_id=chain_nodes[0],
            leaf_id=capsule_id,
            nodes=chain_nodes,
            total_length=len(chain_nodes),
            trust_gradient=trust_gradient
        )
    
    def _get_ancestors(self, capsule_id: str, max_depth: int = 50) -> list[str]:
        """Get all ancestors of a capsule."""
        ancestors = []
        queue = [capsule_id]
        visited = {capsule_id}
        depth = 0
        
        while queue and depth < max_depth:
            current = queue.pop(0)
            node = self._nodes.get(current)
            if not node:
                continue
            
            for parent_id in node.parent_ids:
                if parent_id not in visited and parent_id in self._nodes:
                    visited.add(parent_id)
                    ancestors.append(parent_id)
                    queue.append(parent_id)
            
            depth += 1
        
        return ancestors
    
    def _get_descendants(self, capsule_id: str, max_depth: int = 50) -> list[str]:
        """Get all descendants of a capsule."""
        descendants = []
        queue = [capsule_id]
        visited = {capsule_id}
        depth = 0
        
        while queue and depth < max_depth:
            current = queue.pop(0)
            node = self._nodes.get(current)
            if not node:
                continue
            
            for child_id in node.child_ids:
                if child_id not in visited and child_id in self._nodes:
                    visited.add(child_id)
                    descendants.append(child_id)
                    queue.append(child_id)
            
            depth += 1
        
        return descendants
    
    def _would_create_cycle(self, parent_id: str, child_id: str) -> bool:
        """Check if linking would create a cycle."""
        # Check if child_id is an ancestor of parent_id
        ancestors = self._get_ancestors(parent_id)
        return child_id in ancestors
    
    def _recalculate_depth(self, capsule_id: str) -> None:
        """Recalculate depth for a node and its descendants."""
        if capsule_id not in self._nodes:
            return
        
        node = self._nodes[capsule_id]
        if node.parent_ids:
            parent_depths = [
                self._nodes[pid].depth 
                for pid in node.parent_ids 
                if pid in self._nodes
            ]
            node.depth = max(parent_depths, default=0) + 1
        else:
            node.depth = 0
        
        # Recursively update children
        for child_id in node.child_ids:
            self._recalculate_depth(child_id)
    
    def _update_influence(self, capsule_id: str) -> None:
        """Update influence score for a node."""
        if capsule_id not in self._nodes:
            return
        
        node = self._nodes[capsule_id]
        
        # Simple influence: based on descendants and their trust
        descendants = self._get_descendants(capsule_id, max_depth=10)
        
        if not descendants:
            node.influence_score = 0.0
            node.descendant_count = 0
            return
        
        node.descendant_count = len(descendants)
        
        # Calculate weighted influence
        total_influence = 0.0
        for desc_id in descendants:
            desc_node = self._nodes.get(desc_id)
            if desc_node:
                # Trust-weighted contribution, decaying with depth
                depth_diff = desc_node.depth - node.depth
                decay = (1 - self._trust_decay_rate) ** depth_diff
                total_influence += desc_node.trust_at_creation * decay
        
        node.influence_score = total_influence / 100  # Normalize
    
    def _compute_subtree_metrics(self, root_id: str) -> LineageMetrics:
        """Compute metrics for a subtree."""
        metrics = LineageMetrics(root_id=root_id)
        
        if root_id not in self._nodes:
            return metrics
        
        descendants = self._get_descendants(root_id, max_depth=self.MAX_DEPTH)
        all_nodes = [root_id] + descendants
        
        metrics.total_nodes = len(all_nodes)
        
        # Compute distributions
        depths = []
        children_counts = []
        
        for node_id in all_nodes:
            node = self._nodes.get(node_id)
            if not node:
                continue
            
            depths.append(node.depth)
            children_counts.append(len(node.child_ids))
            
            # By depth
            metrics.nodes_by_depth[node.depth] = \
                metrics.nodes_by_depth.get(node.depth, 0) + 1
            
            # By type
            metrics.nodes_by_type[node.capsule_type] = \
                metrics.nodes_by_type.get(node.capsule_type, 0) + 1
            
            # By creator
            if node.creator_id:
                metrics.nodes_by_creator[node.creator_id] = \
                    metrics.nodes_by_creator.get(node.creator_id, 0) + 1
        
        if depths:
            metrics.max_depth = max(depths)
            metrics.avg_depth = sum(depths) / len(depths)
        
        if children_counts:
            metrics.branching_factor = sum(children_counts) / len(children_counts)
        
        # Compute trust decay
        root_trust = self._nodes[root_id].trust_at_creation
        leaf_trusts = [
            self._nodes[nid].trust_at_creation 
            for nid in all_nodes 
            if not self._nodes[nid].child_ids
        ]
        
        if leaf_trusts and root_trust > 0:
            avg_leaf_trust = sum(leaf_trusts) / len(leaf_trusts)
            metrics.trust_decay = 1 - (avg_leaf_trust / root_trust)
        
        return metrics
    
    def _detect_anomalies(self, capsule_id: str) -> list[LineageAnomaly]:
        """Detect anomalies in lineage."""
        anomalies = []
        
        if capsule_id not in self._nodes:
            return anomalies
        
        node = self._nodes[capsule_id]
        
        # Check for excessive depth
        if node.depth > 50:
            anomalies.append(LineageAnomaly(
                anomaly_type="excessive_depth",
                severity="low",
                affected_nodes=[capsule_id],
                description=f"Capsule has depth {node.depth}, which may indicate over-derivation"
            ))
        
        # Check for rapid derivation
        if node.creator_id:
            recent = self._recent_derivations.get(node.creator_id, [])
            # Clean old entries (last 24h)
            # SECURITY FIX (Audit 2): Removed unsafe __import__() usage
            cutoff = datetime.utcnow() - timedelta(hours=24)
            recent = [t for t in recent if t > cutoff]
            self._recent_derivations[node.creator_id] = recent
            
            if len(recent) > self._max_derivations_per_day:
                anomalies.append(LineageAnomaly(
                    anomaly_type="rapid_derivation",
                    severity="medium",
                    affected_nodes=[capsule_id],
                    description=f"User has created {len(recent)} derivations in 24h"
                ))
        
        # Check for trust spike (child trust >> parent trust)
        for parent_id in node.parent_ids:
            if parent_id in self._nodes:
                parent = self._nodes[parent_id]
                if node.trust_at_creation > parent.trust_at_creation + 20:
                    anomalies.append(LineageAnomaly(
                        anomaly_type="trust_spike",
                        severity="medium",
                        affected_nodes=[capsule_id, parent_id],
                        description=f"Trust increased significantly from parent ({parent.trust_at_creation}) to child ({node.trust_at_creation})"
                    ))
        
        # Check for orphaned references
        for parent_id in node.parent_ids:
            if parent_id not in self._nodes:
                anomalies.append(LineageAnomaly(
                    anomaly_type="broken_chain",
                    severity="high",
                    affected_nodes=[capsule_id, parent_id],
                    description=f"Parent {parent_id} not found in lineage graph"
                ))

        # Check for contradiction involvement
        if node.contradicts:
            anomalies.append(LineageAnomaly(
                anomaly_type="contradiction_detected",
                severity="medium" if len(node.contradicts) == 1 else "high",
                affected_nodes=[capsule_id] + node.contradicts[:5],
                description=f"Capsule has {len(node.contradicts)} contradicting relationships"
            ))

        # Check for high semantic connectivity (potential knowledge hub)
        if node.semantic_connectivity > 20:
            anomalies.append(LineageAnomaly(
                anomaly_type="high_connectivity",
                severity="low",
                affected_nodes=[capsule_id],
                description=f"Capsule has high semantic connectivity ({node.semantic_connectivity} edges)"
            ))

        return anomalies
    
    def get_roots(self) -> list[str]:
        """Get all root capsule IDs."""
        return list(self._roots)
    
    def get_node(self, capsule_id: str) -> Optional[LineageNode]:
        """Get a specific lineage node."""
        return self._nodes.get(capsule_id)
    
    def get_stats(self) -> dict:
        """Get lineage tracking statistics."""
        return {
            **self._stats,
            "nodes_in_memory": len(self._nodes),
            "roots_count": len(self._roots)
        }
    
    def clear_cache(self) -> int:
        """Clear in-memory lineage cache."""
        count = len(self._nodes)
        self._nodes.clear()
        self._roots.clear()
        self._recent_derivations.clear()
        return count


# Convenience function
def create_lineage_tracker(
    strict_mode: bool = False,
    **kwargs
) -> LineageTrackerOverlay:
    """
    Create a lineage tracker overlay.
    
    Args:
        strict_mode: If True, uses stricter anomaly detection
        **kwargs: Additional configuration
        
    Returns:
        Configured LineageTrackerOverlay
    """
    if strict_mode:
        kwargs.setdefault("enable_anomaly_detection", True)
        kwargs.setdefault("trust_decay_rate", 0.1)
        kwargs.setdefault("max_derivations_per_day", 50)
    
    return LineageTrackerOverlay(**kwargs)
