"""
Tests for Lineage Tracker Overlay

Tests the lineage tracking overlay implementation including:
- LineageNode: Capsule lineage node with relationships
- LineageChain: Isnad chain representation
- LineageMetrics: Lineage tree metrics
- LineageAnomaly: Anomaly detection
- LineageTrackerOverlay: Main lineage tracking overlay
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from forge.models.base import CapsuleType
from forge.models.events import Event, EventType
from forge.models.overlay import Capability
from forge.overlays.lineage_tracker import (
    BrokenChainError,
    CircularLineageError,
    LineageAnomaly,
    LineageChain,
    LineageError,
    LineageMetrics,
    LineageNode,
    LineageTrackerOverlay,
    SemanticEdgeInfo,
    create_lineage_tracker,
)
from forge.overlays.base import OverlayContext


# =============================================================================
# SemanticEdgeInfo Tests
# =============================================================================


class TestSemanticEdgeInfo:
    """Tests for SemanticEdgeInfo dataclass."""

    def test_create_edge_info(self):
        """Test creating semantic edge info."""
        edge = SemanticEdgeInfo(
            target_id="capsule-123",
            relationship_type="SUPPORTS",
            confidence=0.9,
            bidirectional=True,
        )

        assert edge.target_id == "capsule-123"
        assert edge.relationship_type == "SUPPORTS"
        assert edge.confidence == 0.9
        assert edge.bidirectional is True

    def test_default_values(self):
        """Test default values."""
        edge = SemanticEdgeInfo(target_id="cap-1", relationship_type="REFERENCES")

        assert edge.confidence == 1.0
        assert edge.bidirectional is False


# =============================================================================
# LineageNode Tests
# =============================================================================


class TestLineageNode:
    """Tests for LineageNode dataclass."""

    def test_create_node_minimal(self):
        """Test creating node with minimal fields."""
        node = LineageNode(
            capsule_id="capsule-123",
            capsule_type="KNOWLEDGE",
        )

        assert node.capsule_id == "capsule-123"
        assert node.capsule_type == "KNOWLEDGE"
        assert node.parent_ids == []
        assert node.child_ids == []
        assert node.depth == 0
        assert node.influence_score == 0.0

    def test_create_node_with_relationships(self):
        """Test creating node with relationships."""
        node = LineageNode(
            capsule_id="capsule-123",
            capsule_type="KNOWLEDGE",
            title="Test Capsule",
            creator_id="user-456",
            parent_ids=["parent-1", "parent-2"],
            child_ids=["child-1"],
            supports=["supported-1"],
            contradicts=["contra-1"],
            depth=2,
            trust_at_creation=80,
        )

        assert node.title == "Test Capsule"
        assert node.creator_id == "user-456"
        assert len(node.parent_ids) == 2
        assert len(node.child_ids) == 1
        assert "supported-1" in node.supports
        assert "contra-1" in node.contradicts
        assert node.depth == 2
        assert node.trust_at_creation == 80


# =============================================================================
# LineageChain Tests
# =============================================================================


class TestLineageChain:
    """Tests for LineageChain dataclass."""

    def test_create_chain(self):
        """Test creating a lineage chain."""
        chain = LineageChain(
            chain_id="chain-123",
            root_id="root-capsule",
            leaf_id="leaf-capsule",
            nodes=["root-capsule", "mid-capsule", "leaf-capsule"],
            total_length=3,
            trust_gradient=[90, 80, 70],
        )

        assert chain.chain_id == "chain-123"
        assert chain.root_id == "root-capsule"
        assert chain.leaf_id == "leaf-capsule"
        assert len(chain.nodes) == 3
        assert chain.total_length == 3
        assert chain.trust_gradient == [90, 80, 70]

    def test_is_valid_true(self):
        """Test is_valid returns True for valid chain."""
        chain = LineageChain(
            chain_id="chain-1",
            root_id="root",
            leaf_id="leaf",
            nodes=["root", "mid", "leaf"],
            total_length=3,
        )

        assert chain.is_valid is True

    def test_is_valid_false_mismatch(self):
        """Test is_valid returns False when lengths mismatch."""
        chain = LineageChain(
            chain_id="chain-1",
            root_id="root",
            leaf_id="leaf",
            nodes=["root", "leaf"],  # Only 2 nodes
            total_length=3,  # But length says 3
        )

        assert chain.is_valid is False

    def test_is_valid_false_empty(self):
        """Test is_valid returns False for empty chain."""
        chain = LineageChain(
            chain_id="chain-1",
            root_id="root",
            leaf_id="leaf",
            nodes=[],
            total_length=0,
        )

        assert chain.is_valid is False


# =============================================================================
# LineageMetrics Tests
# =============================================================================


class TestLineageMetrics:
    """Tests for LineageMetrics dataclass."""

    def test_create_metrics(self):
        """Test creating lineage metrics."""
        metrics = LineageMetrics(
            root_id="root-123",
            total_nodes=50,
            max_depth=5,
            avg_depth=2.5,
            branching_factor=1.8,
            trust_decay=0.15,
            nodes_by_depth={0: 1, 1: 3, 2: 10, 3: 20, 4: 12, 5: 4},
            nodes_by_type={"KNOWLEDGE": 40, "INSIGHT": 10},
        )

        assert metrics.total_nodes == 50
        assert metrics.max_depth == 5
        assert metrics.branching_factor == 1.8
        assert metrics.nodes_by_depth[3] == 20


# =============================================================================
# LineageAnomaly Tests
# =============================================================================


class TestLineageAnomaly:
    """Tests for LineageAnomaly dataclass."""

    def test_create_anomaly(self):
        """Test creating a lineage anomaly."""
        anomaly = LineageAnomaly(
            anomaly_type="circular",
            severity="high",
            affected_nodes=["node-1", "node-2"],
            description="Circular reference detected",
        )

        assert anomaly.anomaly_type == "circular"
        assert anomaly.severity == "high"
        assert len(anomaly.affected_nodes) == 2
        assert anomaly.detected_at is not None


# =============================================================================
# LineageTrackerOverlay Tests
# =============================================================================


class TestLineageTrackerOverlay:
    """Tests for LineageTrackerOverlay class."""

    @pytest.fixture
    def overlay(self):
        """Create a lineage tracker overlay for testing."""
        return LineageTrackerOverlay()

    @pytest.fixture
    def context(self, overlay):
        """Create an execution context."""
        return OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-123",
            triggered_by="manual",
            correlation_id="corr-123",
            user_id="user-123",
            trust_flame=70,
            capabilities={
                Capability.DATABASE_READ,
                Capability.DATABASE_WRITE,
            },
        )

    def test_overlay_attributes(self, overlay):
        """Test overlay has correct attributes."""
        assert overlay.NAME == "lineage_tracker"
        assert overlay.VERSION == "1.0.0"
        assert EventType.CAPSULE_CREATED in overlay.SUBSCRIBED_EVENTS
        assert EventType.CAPSULE_LINKED in overlay.SUBSCRIBED_EVENTS
        assert EventType.SEMANTIC_EDGE_CREATED in overlay.SUBSCRIBED_EVENTS
        assert Capability.DATABASE_READ in overlay.REQUIRED_CAPABILITIES

    @pytest.mark.asyncio
    async def test_initialize(self, overlay):
        """Test overlay initialization."""
        result = await overlay.initialize()
        assert result is True

    @pytest.mark.asyncio
    async def test_handle_capsule_created_root(self, overlay, context):
        """Test handling capsule creation as root node."""
        await overlay.initialize()

        event = Event(
            id="event-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "capsule-123",
                "type": "KNOWLEDGE",
                "title": "Test Capsule",
            },
        )

        result = await overlay.execute(context, event=event)

        assert result.success is True
        assert result.data["capsule_id"] == "capsule-123"
        assert result.data["is_root"] is True
        assert result.data["depth"] == 0

    @pytest.mark.asyncio
    async def test_handle_capsule_created_with_parent(self, overlay, context):
        """Test handling capsule creation with parent."""
        await overlay.initialize()

        # Create parent first
        parent_event = Event(
            id="event-1",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "parent-123", "type": "KNOWLEDGE"},
        )
        await overlay.execute(context, event=parent_event)

        # Create child with parent
        child_event = Event(
            id="event-2",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "child-123",
                "type": "KNOWLEDGE",
                "parent_id": "parent-123",
            },
        )

        result = await overlay.execute(context, event=child_event)

        assert result.success is True
        assert result.data["is_root"] is False
        assert result.data["depth"] == 1
        assert result.data["parent_count"] == 1

    @pytest.mark.asyncio
    async def test_handle_capsule_linked(self, overlay, context):
        """Test handling capsule linking."""
        await overlay.initialize()

        # Create two capsules
        for capsule_id in ["cap-1", "cap-2"]:
            event = Event(
                id=f"event-{capsule_id}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": capsule_id, "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Link them
        link_event = Event(
            id="link-event",
            type=EventType.CAPSULE_LINKED,
            source="test",
            payload={
                "parent_id": "cap-1",
                "child_id": "cap-2",
            },
        )

        result = await overlay.execute(context, event=link_event)

        assert result.success is True
        assert result.data["linked"] is True

    @pytest.mark.asyncio
    async def test_handle_capsule_linked_circular_detection(self, overlay, context):
        """Test circular reference detection in linking."""
        await overlay.initialize()

        # Create chain: cap-1 -> cap-2 -> cap-3
        for i, capsule_id in enumerate(["cap-1", "cap-2", "cap-3"]):
            parent_id = f"cap-{i}" if i > 0 else None
            event = Event(
                id=f"event-{capsule_id}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={
                    "capsule_id": capsule_id,
                    "type": "KNOWLEDGE",
                    "parent_id": parent_id,
                },
            )
            await overlay.execute(context, event=event)

        # Try to create cycle: cap-1 -> cap-3 (would make cap-1 child of its descendant)
        link_event = Event(
            id="link-event",
            type=EventType.CAPSULE_LINKED,
            source="test",
            payload={
                "parent_id": "cap-3",
                "child_id": "cap-1",  # cap-1 is ancestor of cap-3
            },
        )

        result = await overlay.execute(context, event=link_event)

        assert "circular" in result.data.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_handle_semantic_edge_created(self, overlay, context):
        """Test handling semantic edge creation."""
        await overlay.initialize()

        # Create two capsules
        for capsule_id in ["source-cap", "target-cap"]:
            event = Event(
                id=f"event-{capsule_id}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": capsule_id, "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Create semantic edge
        edge_event = Event(
            id="edge-event",
            type=EventType.SEMANTIC_EDGE_CREATED,
            source="test",
            payload={
                "source_id": "source-cap",
                "target_id": "target-cap",
                "relationship_type": "SUPPORTS",
                "confidence": 0.9,
            },
        )

        result = await overlay.execute(context, event=edge_event)

        assert result.success is True
        assert result.data["edge_tracked"] is True
        assert result.data["relationship_type"] == "SUPPORTS"

    @pytest.mark.asyncio
    async def test_handle_semantic_edge_bidirectional(self, overlay, context):
        """Test bidirectional semantic edge creation."""
        await overlay.initialize()

        # Create two capsules
        for capsule_id in ["cap-a", "cap-b"]:
            event = Event(
                id=f"event-{capsule_id}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": capsule_id, "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Create bidirectional edge
        edge_event = Event(
            id="edge-event",
            type=EventType.SEMANTIC_EDGE_CREATED,
            source="test",
            payload={
                "source_id": "cap-a",
                "target_id": "cap-b",
                "relationship_type": "RELATED_TO",
                "bidirectional": True,
            },
        )

        result = await overlay.execute(context, event=edge_event)

        assert result.success is True
        assert result.data["bidirectional"] is True

        # Check both nodes have edges
        node_a = overlay.get_node("cap-a")
        node_b = overlay.get_node("cap-b")
        assert node_a.semantic_connectivity >= 1
        assert node_b.semantic_connectivity >= 1

    @pytest.mark.asyncio
    async def test_compute_chain_to_root(self, overlay, context):
        """Test computing Isnad chain to root."""
        await overlay.initialize()

        # Create a chain of 4 capsules
        for i in range(4):
            parent_id = f"cap-{i-1}" if i > 0 else None
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={
                    "capsule_id": f"cap-{i}",
                    "type": "KNOWLEDGE",
                    "parent_id": parent_id,
                },
            )
            await overlay.execute(context, event=event)

        # Get lineage info for leaf
        result = await overlay.execute(context, input_data={"capsule_id": "cap-3"})

        assert result.success is True
        isnad = result.data["isnad"]
        assert isnad["root_id"] == "cap-0"
        assert isnad["length"] == 4

    @pytest.mark.asyncio
    async def test_compute_semantic_distance(self, overlay, context):
        """Test computing semantic distance between capsules."""
        await overlay.initialize()

        # Create connected capsules
        for capsule_id in ["start", "middle", "end"]:
            event = Event(
                id=f"event-{capsule_id}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": capsule_id, "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Create edges: start -> middle -> end
        for source, target in [("start", "middle"), ("middle", "end")]:
            edge_event = Event(
                id=f"edge-{source}-{target}",
                type=EventType.SEMANTIC_EDGE_CREATED,
                source="test",
                payload={
                    "source_id": source,
                    "target_id": target,
                    "relationship_type": "REFERENCES",
                },
            )
            await overlay.execute(context, event=edge_event)

        # Compute distance
        distance_result = overlay.compute_semantic_distance("start", "end", max_hops=5)

        assert distance_result["found"] is True
        assert distance_result["distance"] == 2

    @pytest.mark.asyncio
    async def test_find_contradiction_clusters(self, overlay, context):
        """Test finding contradiction clusters."""
        await overlay.initialize()

        # Create capsules
        for capsule_id in ["a", "b", "c", "d"]:
            event = Event(
                id=f"event-{capsule_id}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": capsule_id, "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Create contradiction edges: a <-> b, b <-> c (forms cluster)
        for source, target in [("a", "b"), ("b", "c")]:
            edge_event = Event(
                id=f"contra-{source}-{target}",
                type=EventType.SEMANTIC_EDGE_CREATED,
                source="test",
                payload={
                    "source_id": source,
                    "target_id": target,
                    "relationship_type": "CONTRADICTS",
                },
            )
            await overlay.execute(context, event=edge_event)

        clusters = overlay.find_contradiction_clusters(min_size=2)

        assert len(clusters) >= 1
        # At least a-b cluster
        cluster_sizes = [c["size"] for c in clusters]
        assert max(cluster_sizes) >= 2

    @pytest.mark.asyncio
    async def test_anomaly_detection_excessive_depth(self, overlay, context):
        """Test anomaly detection for excessive depth."""
        overlay = LineageTrackerOverlay(enable_anomaly_detection=True)
        await overlay.initialize()

        # Create very deep chain (> 50)
        for i in range(55):
            parent_id = f"cap-{i-1}" if i > 0 else None
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={
                    "capsule_id": f"cap-{i}",
                    "type": "KNOWLEDGE",
                    "parent_id": parent_id,
                },
            )
            await overlay.execute(context, event=event)

        # Check for anomaly
        anomalies = overlay._detect_anomalies("cap-54")

        anomaly_types = [a.anomaly_type for a in anomalies]
        assert "excessive_depth" in anomaly_types

    @pytest.mark.asyncio
    async def test_anomaly_detection_rapid_derivation(self, overlay, context):
        """Test anomaly detection for rapid derivation."""
        overlay = LineageTrackerOverlay(
            enable_anomaly_detection=True, max_derivations_per_day=5
        )
        await overlay.initialize()

        # Create many capsules rapidly
        for i in range(10):
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={
                    "capsule_id": f"rapid-cap-{i}",
                    "type": "KNOWLEDGE",
                },
            )
            await overlay.execute(context, event=event)

        # Check for anomaly on last created
        anomalies = overlay._detect_anomalies("rapid-cap-9")

        anomaly_types = [a.anomaly_type for a in anomalies]
        assert "rapid_derivation" in anomaly_types

    @pytest.mark.asyncio
    async def test_anomaly_detection_trust_spike(self, overlay, context):
        """Test anomaly detection for trust spike."""
        overlay = LineageTrackerOverlay(enable_anomaly_detection=True)
        await overlay.initialize()

        # Create parent with low trust
        low_trust_context = OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-1",
            triggered_by="manual",
            correlation_id="corr-1",
            user_id="user-1",
            trust_flame=40,  # Low trust
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )

        parent_event = Event(
            id="parent-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={"capsule_id": "low-trust-parent", "type": "KNOWLEDGE"},
        )
        await overlay.execute(low_trust_context, event=parent_event)

        # Create child with much higher trust
        high_trust_context = OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-2",
            triggered_by="manual",
            correlation_id="corr-2",
            user_id="user-2",
            trust_flame=90,  # Much higher trust (spike > 20)
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )

        child_event = Event(
            id="child-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "high-trust-child",
                "type": "KNOWLEDGE",
                "parent_id": "low-trust-parent",
            },
        )
        await overlay.execute(high_trust_context, event=child_event)

        # Check for anomaly
        anomalies = overlay._detect_anomalies("high-trust-child")

        anomaly_types = [a.anomaly_type for a in anomalies]
        assert "trust_spike" in anomaly_types

    @pytest.mark.asyncio
    async def test_get_lineage_info_not_found(self, overlay, context):
        """Test get lineage info for non-existent capsule."""
        await overlay.initialize()

        result = await overlay.execute(
            context, input_data={"capsule_id": "non-existent"}
        )

        assert result.success is True
        assert result.data["found"] is False

    @pytest.mark.asyncio
    async def test_get_lineage_info_overall_stats(self, overlay, context):
        """Test get lineage info without capsule_id returns stats."""
        await overlay.initialize()

        # Create a few capsules
        for i in range(3):
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": f"cap-{i}", "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        result = await overlay.execute(context, input_data={})

        assert result.success is True
        assert result.data["total_nodes"] == 3
        assert "stats" in result.data

    def test_get_roots(self, overlay):
        """Test getting root capsule IDs."""
        # Manually add some nodes
        overlay._nodes["root-1"] = LineageNode(
            capsule_id="root-1", capsule_type="KNOWLEDGE"
        )
        overlay._nodes["root-2"] = LineageNode(
            capsule_id="root-2", capsule_type="KNOWLEDGE"
        )
        overlay._roots = {"root-1", "root-2"}

        roots = overlay.get_roots()

        assert len(roots) == 2
        assert "root-1" in roots
        assert "root-2" in roots

    def test_get_node(self, overlay):
        """Test getting a specific node."""
        overlay._nodes["test-cap"] = LineageNode(
            capsule_id="test-cap", capsule_type="KNOWLEDGE", title="Test"
        )

        node = overlay.get_node("test-cap")

        assert node is not None
        assert node.title == "Test"

    def test_get_node_not_found(self, overlay):
        """Test getting non-existent node returns None."""
        node = overlay.get_node("non-existent")
        assert node is None

    def test_get_stats(self, overlay):
        """Test getting statistics."""
        stats = overlay.get_stats()

        assert "nodes_tracked" in stats
        assert "chains_computed" in stats
        assert "anomalies_detected" in stats
        assert "nodes_in_memory" in stats

    def test_clear_cache(self, overlay):
        """Test clearing the lineage cache."""
        # Add some nodes
        overlay._nodes["cap-1"] = LineageNode(
            capsule_id="cap-1", capsule_type="KNOWLEDGE"
        )
        overlay._roots.add("cap-1")

        count = overlay.clear_cache()

        assert count == 1
        assert len(overlay._nodes) == 0
        assert len(overlay._roots) == 0


# =============================================================================
# Memory Management Tests
# =============================================================================


class TestLineageMemoryManagement:
    """Tests for memory management in LineageTrackerOverlay."""

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction when node limit is reached."""
        # Create overlay with small node limit
        overlay = LineageTrackerOverlay()
        overlay._MAX_NODES = 10

        await overlay.initialize()

        context = OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-123",
            triggered_by="manual",
            correlation_id="corr-123",
            user_id="user-123",
            trust_flame=70,
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )

        # Create more nodes than limit
        for i in range(15):
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": f"cap-{i}", "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Should have evicted some nodes
        assert overlay._stats["nodes_evicted"] > 0
        assert len(overlay._nodes) <= overlay._MAX_NODES

    @pytest.mark.asyncio
    async def test_derivation_tracking_bounded(self):
        """Test derivation tracking is bounded per user."""
        overlay = LineageTrackerOverlay()
        overlay._MAX_DERIVATIONS_PER_USER = 5

        await overlay.initialize()

        context = OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-123",
            triggered_by="manual",
            correlation_id="corr-123",
            user_id="test-user",
            trust_flame=70,
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )

        # Create many capsules
        for i in range(10):
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": f"cap-{i}", "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Should only track last N derivations per user
        assert len(overlay._recent_derivations["test-user"]) <= 5

    @pytest.mark.asyncio
    async def test_evict_lru_nodes(self):
        """Test explicit LRU eviction."""
        overlay = LineageTrackerOverlay()
        await overlay.initialize()

        # Add some nodes
        for i in range(10):
            overlay._nodes[f"cap-{i}"] = LineageNode(
                capsule_id=f"cap-{i}", capsule_type="KNOWLEDGE"
            )
            overlay._nodes_access_order.append(f"cap-{i}")

        # Evict 5 nodes
        evicted = overlay._evict_lru_nodes(count=5)

        assert evicted == 5
        assert len(overlay._nodes) == 5
        # First 5 should be evicted
        assert "cap-0" not in overlay._nodes
        assert "cap-4" not in overlay._nodes
        # Last 5 should remain
        assert "cap-5" in overlay._nodes
        assert "cap-9" in overlay._nodes


# =============================================================================
# Depth Recalculation Tests
# =============================================================================


class TestDepthRecalculation:
    """Tests for depth recalculation."""

    @pytest.mark.asyncio
    async def test_recalculate_depth_iterative(self):
        """Test iterative depth recalculation (BFS)."""
        overlay = LineageTrackerOverlay()
        await overlay.initialize()

        # Create a tree structure manually
        #     root
        #    /    \
        #  c1      c2
        #  /
        # c3
        overlay._nodes["root"] = LineageNode(
            capsule_id="root", capsule_type="KNOWLEDGE", child_ids=["c1", "c2"], depth=0
        )
        overlay._nodes["c1"] = LineageNode(
            capsule_id="c1",
            capsule_type="KNOWLEDGE",
            parent_ids=["root"],
            child_ids=["c3"],
            depth=1,
        )
        overlay._nodes["c2"] = LineageNode(
            capsule_id="c2",
            capsule_type="KNOWLEDGE",
            parent_ids=["root"],
            depth=1,
        )
        overlay._nodes["c3"] = LineageNode(
            capsule_id="c3",
            capsule_type="KNOWLEDGE",
            parent_ids=["c1"],
            depth=2,
        )

        # Reset depths to 0
        for node in overlay._nodes.values():
            node.depth = 0

        # Recalculate from root
        overlay._recalculate_depth("root")

        # Check depths
        assert overlay._nodes["root"].depth == 0
        assert overlay._nodes["c1"].depth == 1
        assert overlay._nodes["c2"].depth == 1
        assert overlay._nodes["c3"].depth == 2


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestCreateLineageTracker:
    """Tests for create_lineage_tracker factory function."""

    def test_create_default(self):
        """Test creating tracker with defaults."""
        tracker = create_lineage_tracker()

        assert tracker.NAME == "lineage_tracker"
        assert tracker._enable_anomaly_detection is True

    def test_create_strict_mode(self):
        """Test creating tracker in strict mode."""
        tracker = create_lineage_tracker(strict_mode=True)

        assert tracker._enable_anomaly_detection is True
        assert tracker._trust_decay_rate == 0.1
        assert tracker._max_derivations_per_day == 50

    def test_create_with_custom_settings(self):
        """Test creating tracker with custom settings."""
        tracker = create_lineage_tracker(
            enable_anomaly_detection=False,
            trust_decay_rate=0.2,
            max_derivations_per_day=25,
        )

        assert tracker._enable_anomaly_detection is False
        assert tracker._trust_decay_rate == 0.2
        assert tracker._max_derivations_per_day == 25


# =============================================================================
# Exception Tests
# =============================================================================


class TestLineageExceptions:
    """Tests for lineage exception classes."""

    def test_lineage_error(self):
        """Test LineageError base exception."""
        error = LineageError("Base error")
        assert str(error) == "Base error"

    def test_circular_lineage_error(self):
        """Test CircularLineageError exception."""
        error = CircularLineageError("Circular reference")
        assert isinstance(error, LineageError)

    def test_broken_chain_error(self):
        """Test BrokenChainError exception."""
        error = BrokenChainError("Chain broken")
        assert isinstance(error, LineageError)


# =============================================================================
# Integration Tests
# =============================================================================


class TestLineageTrackerIntegration:
    """Integration tests for lineage tracking."""

    @pytest.mark.asyncio
    async def test_full_lineage_workflow(self):
        """Test complete lineage tracking workflow."""
        overlay = LineageTrackerOverlay(
            enable_anomaly_detection=True, enable_metrics=True
        )
        await overlay.initialize()

        context = OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-123",
            triggered_by="manual",
            correlation_id="corr-123",
            user_id="user-123",
            trust_flame=70,
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )

        # 1. Create root capsule
        root_event = Event(
            id="root-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "root",
                "type": "KNOWLEDGE",
                "title": "Root Capsule",
            },
        )
        await overlay.execute(context, event=root_event)

        # 2. Create child capsules
        for i in range(3):
            child_event = Event(
                id=f"child-event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={
                    "capsule_id": f"child-{i}",
                    "type": "INSIGHT",
                    "parent_id": "root",
                },
            )
            await overlay.execute(context, event=child_event)

        # 3. Create grandchild
        grandchild_event = Event(
            id="grandchild-event",
            type=EventType.CAPSULE_CREATED,
            source="test",
            payload={
                "capsule_id": "grandchild",
                "type": "DECISION",
                "parent_id": "child-0",
            },
        )
        await overlay.execute(context, event=grandchild_event)

        # 4. Add semantic edges
        edge_event = Event(
            id="edge-event",
            type=EventType.SEMANTIC_EDGE_CREATED,
            source="test",
            payload={
                "source_id": "child-1",
                "target_id": "child-2",
                "relationship_type": "SUPPORTS",
            },
        )
        await overlay.execute(context, event=edge_event)

        # 5. Query lineage info
        result = await overlay.execute(context, input_data={"capsule_id": "grandchild"})

        assert result.success is True
        assert result.data["node"]["depth"] == 2
        assert result.data["isnad"]["root_id"] == "root"
        assert result.data["isnad"]["length"] == 3  # root -> child-0 -> grandchild
        assert "metrics" in result.data

    @pytest.mark.asyncio
    async def test_cascade_event_handling(self):
        """Test handling cascade events updates lineage."""
        overlay = LineageTrackerOverlay(enable_metrics=True)
        await overlay.initialize()

        context = OverlayContext(
            overlay_id=overlay.id,
            overlay_name=overlay.NAME,
            execution_id="exec-123",
            triggered_by="manual",
            correlation_id="corr-123",
            user_id="user-123",
            trust_flame=70,
            capabilities={Capability.DATABASE_READ, Capability.DATABASE_WRITE},
        )

        # Create some capsules
        for i in range(3):
            event = Event(
                id=f"event-{i}",
                type=EventType.CAPSULE_CREATED,
                source="test",
                payload={"capsule_id": f"cap-{i}", "type": "KNOWLEDGE"},
            )
            await overlay.execute(context, event=event)

        # Trigger cascade event
        cascade_event = Event(
            id="cascade-event",
            type=EventType.CASCADE_TRIGGERED,
            source="test",
            payload={
                "source_id": "cap-0",
                "affected_ids": ["cap-1", "cap-2"],
            },
        )

        result = await overlay.execute(context, event=cascade_event)

        assert result.success is True
        assert result.data["cascade_processed"] is True
        assert result.data["affected_count"] == 2
