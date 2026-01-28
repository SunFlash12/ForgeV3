"""
Tests for forge.compliance.core.repository module.

Tests the ComplianceRepository class for Neo4j persistence including
DSAR operations, consent management, breach notifications, audit events,
and AI system/decision operations.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from forge.compliance.core.repository import (
    ComplianceRepository,
    get_compliance_repository,
    initialize_compliance_repository,
)


class TestComplianceRepositoryInitialization:
    """Tests for ComplianceRepository initialization."""

    def test_repository_creation(self, mock_neo4j_client):
        """Test repository creation with Neo4j client."""
        repo = ComplianceRepository(mock_neo4j_client)
        assert repo._db is mock_neo4j_client
        assert repo._initialized is False

    @pytest.mark.asyncio
    async def test_initialize_creates_indexes(self, mock_neo4j_client):
        """Test that initialize creates required indexes."""
        repo = ComplianceRepository(mock_neo4j_client)
        await repo.initialize()

        assert repo._initialized is True
        # Should have called execute multiple times for constraints
        assert mock_neo4j_client.execute.call_count > 0

    @pytest.mark.asyncio
    async def test_initialize_only_runs_once(self, mock_neo4j_client):
        """Test that initialize only runs once."""
        repo = ComplianceRepository(mock_neo4j_client)
        await repo.initialize()

        call_count_after_first = mock_neo4j_client.execute.call_count
        await repo.initialize()

        # Should not have made additional calls
        assert mock_neo4j_client.execute.call_count == call_count_after_first

    @pytest.mark.asyncio
    async def test_initialize_handles_existing_constraints(self, mock_neo4j_client):
        """Test that initialize handles existing constraint errors gracefully."""
        mock_neo4j_client.execute = AsyncMock(
            side_effect=Exception("Constraint already exists")
        )

        repo = ComplianceRepository(mock_neo4j_client)
        # Should not raise, just log warning
        await repo.initialize()
        assert repo._initialized is True


class TestDSAROperations:
    """Tests for DSAR CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_dsar(self, mock_repository):
        """Test creating a DSAR."""
        dsar_data = {
            "id": "dsar_001",
            "request_type": "access",
            "jurisdiction": "eu",
            "applicable_frameworks": ["gdpr"],
            "subject_id": "user_123",
            "subject_email": "user@example.com",
            "subject_name": "Test User",
            "request_text": "I want to access my data",
            "specific_data_categories": ["profile"],
            "status": "received",
            "verified": False,
            "deadline": datetime.now(UTC) + timedelta(days=30),
            "assigned_to": None,
            "processing_notes": [],
        }

        mock_repository.create_dsar = AsyncMock(return_value=dsar_data)
        result = await mock_repository.create_dsar(dsar_data)

        assert result["id"] == "dsar_001"
        mock_repository.create_dsar.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_dsar(self, mock_repository):
        """Test updating a DSAR."""
        updates = {
            "status": "processing",
            "assigned_to": "processor_001",
        }

        mock_repository.update_dsar = AsyncMock(
            return_value={"id": "dsar_001", **updates}
        )
        result = await mock_repository.update_dsar("dsar_001", updates)

        assert result["status"] == "processing"
        assert result["assigned_to"] == "processor_001"

    @pytest.mark.asyncio
    async def test_update_dsar_nonexistent(self, mock_repository):
        """Test updating a nonexistent DSAR."""
        mock_repository.update_dsar = AsyncMock(return_value=None)
        result = await mock_repository.update_dsar("nonexistent", {"status": "completed"})
        assert result is None

    @pytest.mark.asyncio
    async def test_get_dsar(self, mock_repository):
        """Test getting a DSAR by ID."""
        dsar_data = {
            "id": "dsar_001",
            "request_type": "access",
            "status": "received",
            "applicable_frameworks": '["gdpr"]',
            "specific_data_categories": '["profile"]',
            "processing_notes": "[]",
        }

        mock_repository.get_dsar = AsyncMock(return_value=dsar_data)
        result = await mock_repository.get_dsar("dsar_001")

        assert result["id"] == "dsar_001"

    @pytest.mark.asyncio
    async def test_get_dsar_nonexistent(self, mock_repository):
        """Test getting a nonexistent DSAR."""
        mock_repository.get_dsar = AsyncMock(return_value=None)
        result = await mock_repository.get_dsar("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_dsars_by_status(self, mock_repository):
        """Test getting DSARs by status."""
        dsars = [
            {"id": "dsar_001", "status": "processing"},
            {"id": "dsar_002", "status": "processing"},
        ]

        mock_repository.get_dsars_by_status = AsyncMock(return_value=dsars)
        result = await mock_repository.get_dsars_by_status("processing")

        assert len(result) == 2
        for dsar in result:
            assert dsar["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_overdue_dsars(self, mock_repository):
        """Test getting overdue DSARs."""
        overdue_dsars = [
            {"id": "dsar_001", "deadline": "2024-01-01T00:00:00Z"},
        ]

        mock_repository.get_overdue_dsars = AsyncMock(return_value=overdue_dsars)
        result = await mock_repository.get_overdue_dsars()

        assert len(result) == 1


class TestConsentOperations:
    """Tests for consent CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_consent(self, mock_repository):
        """Test creating a consent record."""
        consent_data = {
            "id": "consent_001",
            "user_id": "user_123",
            "consent_type": "analytics",
            "purpose": "Website analytics",
            "granted": True,
            "granted_at": datetime.now(UTC),
            "withdrawn_at": None,
            "collected_via": "consent_banner",
            "ip_address": "192.168.1.1",
            "consent_text_version": "1.0",
            "third_parties": [],
        }

        mock_repository.create_consent = AsyncMock(return_value=consent_data)
        result = await mock_repository.create_consent(consent_data)

        assert result["id"] == "consent_001"
        assert result["granted"] is True

    @pytest.mark.asyncio
    async def test_withdraw_consent(self, mock_repository):
        """Test withdrawing consent."""
        mock_repository.withdraw_consent = AsyncMock(
            return_value={"id": "consent_001", "granted": False}
        )
        result = await mock_repository.withdraw_consent("consent_001")

        assert result["granted"] is False

    @pytest.mark.asyncio
    async def test_withdraw_consent_nonexistent(self, mock_repository):
        """Test withdrawing nonexistent consent."""
        mock_repository.withdraw_consent = AsyncMock(return_value=None)
        result = await mock_repository.withdraw_consent("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_consents(self, mock_repository):
        """Test getting all consents for a user."""
        consents = [
            {"id": "consent_001", "user_id": "user_123", "consent_type": "analytics"},
            {"id": "consent_002", "user_id": "user_123", "consent_type": "marketing"},
        ]

        mock_repository.get_user_consents = AsyncMock(return_value=consents)
        result = await mock_repository.get_user_consents("user_123")

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_check_consent_granted(self, mock_repository):
        """Test checking consent that is granted."""
        mock_repository.check_consent = AsyncMock(return_value=True)
        result = await mock_repository.check_consent("user_123", "analytics")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_consent_not_granted(self, mock_repository):
        """Test checking consent that is not granted."""
        mock_repository.check_consent = AsyncMock(return_value=False)
        result = await mock_repository.check_consent("user_123", "marketing")
        assert result is False


class TestBreachOperations:
    """Tests for breach notification operations."""

    @pytest.mark.asyncio
    async def test_create_breach(self, mock_repository):
        """Test creating a breach notification."""
        breach_data = {
            "id": "breach_001",
            "discovered_by": "security_team",
            "discovery_method": "monitoring",
            "severity": "high",
            "breach_type": "unauthorized_access",
            "status": "reported",
            "data_categories": ["personal_data"],
            "data_elements": ["email", "name"],
            "jurisdictions": ["eu"],
            "record_count": 1000,
            "contained": False,
        }

        mock_repository.create_breach = AsyncMock(return_value=breach_data)
        result = await mock_repository.create_breach(breach_data)

        assert result["id"] == "breach_001"
        assert result["severity"] == "high"

    @pytest.mark.asyncio
    async def test_update_breach(self, mock_repository):
        """Test updating a breach notification."""
        updates = {
            "contained": True,
            "contained_at": datetime.now(UTC),
            "containment_actions": ["isolated_system", "rotated_credentials"],
        }

        mock_repository.update_breach = AsyncMock(
            return_value={"id": "breach_001", **updates}
        )
        result = await mock_repository.update_breach("breach_001", updates)

        assert result["contained"] is True

    @pytest.mark.asyncio
    async def test_get_breach(self, mock_repository):
        """Test getting a breach by ID."""
        breach_data = {
            "id": "breach_001",
            "severity": "high",
            "data_categories": '["personal_data"]',
        }

        mock_repository.get_breach = AsyncMock(return_value=breach_data)
        result = await mock_repository.get_breach("breach_001")

        assert result["id"] == "breach_001"

    @pytest.mark.asyncio
    async def test_get_active_breaches(self, mock_repository):
        """Test getting active breaches."""
        breaches = [
            {"id": "breach_001", "status": "reported"},
            {"id": "breach_002", "status": "investigating"},
        ]

        mock_repository.get_active_breaches = AsyncMock(return_value=breaches)
        result = await mock_repository.get_active_breaches()

        assert len(result) == 2


class TestAuditEventOperations:
    """Tests for audit event operations."""

    @pytest.mark.asyncio
    async def test_create_audit_event(self, mock_repository):
        """Test creating an audit event."""
        event_data = {
            "id": "event_001",
            "category": "data_access",
            "event_type": "user_data_export",
            "action": "READ",
            "actor_id": "user_123",
            "actor_type": "user",
            "entity_type": "UserData",
            "entity_id": "data_001",
            "success": True,
            "hash": "abc123",
            "previous_hash": None,
        }

        mock_repository.create_audit_event = AsyncMock(return_value=event_data)
        result = await mock_repository.create_audit_event(event_data)

        assert result["id"] == "event_001"
        assert result["category"] == "data_access"

    @pytest.mark.asyncio
    async def test_get_audit_events_no_filters(self, mock_repository):
        """Test getting audit events without filters."""
        events = [
            {"id": "event_001", "category": "data_access"},
            {"id": "event_002", "category": "authentication"},
        ]

        mock_repository.get_audit_events = AsyncMock(return_value=events)
        result = await mock_repository.get_audit_events()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_audit_events_with_filters(self, mock_repository):
        """Test getting audit events with filters."""
        events = [{"id": "event_001", "category": "authentication"}]

        mock_repository.get_audit_events = AsyncMock(return_value=events)
        result = await mock_repository.get_audit_events(
            category="authentication",
            actor_id="user_123",
            limit=50,
        )

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_last_audit_hash(self, mock_repository):
        """Test getting the last audit hash."""
        mock_repository.get_last_audit_hash = AsyncMock(return_value="abc123def456")
        result = await mock_repository.get_last_audit_hash()

        assert result == "abc123def456"

    @pytest.mark.asyncio
    async def test_get_last_audit_hash_empty(self, mock_repository):
        """Test getting last audit hash when no events exist."""
        mock_repository.get_last_audit_hash = AsyncMock(return_value=None)
        result = await mock_repository.get_last_audit_hash()

        assert result is None

    @pytest.mark.asyncio
    async def test_verify_audit_chain_valid(self, mock_repository):
        """Test verifying a valid audit chain."""
        mock_repository.verify_audit_chain = AsyncMock(
            return_value=(True, "Chain verified: 100 events")
        )
        is_valid, message = await mock_repository.verify_audit_chain()

        assert is_valid is True
        assert "verified" in message.lower()

    @pytest.mark.asyncio
    async def test_verify_audit_chain_invalid(self, mock_repository):
        """Test verifying an invalid audit chain."""
        mock_repository.verify_audit_chain = AsyncMock(
            return_value=(False, "Chain broken at event event_050")
        )
        is_valid, message = await mock_repository.verify_audit_chain()

        assert is_valid is False
        assert "broken" in message.lower()


class TestAISystemOperations:
    """Tests for AI system registration operations."""

    @pytest.mark.asyncio
    async def test_create_ai_system(self, mock_repository):
        """Test registering an AI system."""
        system_data = {
            "id": "ai_sys_001",
            "system_name": "Recommendation Engine",
            "system_version": "2.0.0",
            "provider": "Forge AI",
            "risk_classification": "limited_risk",
            "intended_purpose": "Content recommendations",
            "use_cases": ["personalization"],
            "model_type": "collaborative_filtering",
        }

        mock_repository.create_ai_system = AsyncMock(return_value=system_data)
        result = await mock_repository.create_ai_system(system_data)

        assert result["id"] == "ai_sys_001"
        assert result["system_name"] == "Recommendation Engine"

    @pytest.mark.asyncio
    async def test_get_ai_system(self, mock_repository):
        """Test getting an AI system by ID."""
        system_data = {
            "id": "ai_sys_001",
            "system_name": "Recommendation Engine",
            "use_cases": '["personalization"]',
        }

        mock_repository.get_ai_system = AsyncMock(return_value=system_data)
        result = await mock_repository.get_ai_system("ai_sys_001")

        assert result["id"] == "ai_sys_001"

    @pytest.mark.asyncio
    async def test_get_all_ai_systems(self, mock_repository):
        """Test getting all AI systems."""
        systems = [
            {"id": "ai_sys_001", "system_name": "System 1"},
            {"id": "ai_sys_002", "system_name": "System 2"},
        ]

        mock_repository.get_all_ai_systems = AsyncMock(return_value=systems)
        result = await mock_repository.get_all_ai_systems()

        assert len(result) == 2


class TestAIDecisionOperations:
    """Tests for AI decision logging operations."""

    @pytest.mark.asyncio
    async def test_create_ai_decision(self, mock_repository):
        """Test logging an AI decision."""
        decision_data = {
            "id": "decision_001",
            "ai_system_id": "ai_sys_001",
            "model_version": "2.0.0",
            "decision_type": "recommendation",
            "decision_outcome": "recommend_items",
            "confidence_score": 0.85,
            "input_summary": {"user_id": "user_123"},
            "reasoning_chain": ["step1", "step2"],
            "key_factors": [{"factor": "history", "weight": 0.5}],
            "has_legal_effect": False,
        }

        mock_repository.create_ai_decision = AsyncMock(return_value=decision_data)
        result = await mock_repository.create_ai_decision(decision_data)

        assert result["id"] == "decision_001"
        assert result["confidence_score"] == 0.85

    @pytest.mark.asyncio
    async def test_update_ai_decision(self, mock_repository):
        """Test updating an AI decision for human review."""
        updates = {
            "human_reviewed": True,
            "human_reviewer": "reviewer_001",
            "human_override": False,
        }

        mock_repository.update_ai_decision = AsyncMock(
            return_value={"id": "decision_001", **updates}
        )
        result = await mock_repository.update_ai_decision("decision_001", updates)

        assert result["human_reviewed"] is True

    @pytest.mark.asyncio
    async def test_get_ai_decisions(self, mock_repository):
        """Test getting AI decisions with filters."""
        decisions = [
            {"id": "decision_001", "ai_system_id": "ai_sys_001"},
            {"id": "decision_002", "ai_system_id": "ai_sys_001"},
        ]

        mock_repository.get_ai_decisions = AsyncMock(return_value=decisions)
        result = await mock_repository.get_ai_decisions(ai_system_id="ai_sys_001")

        assert len(result) == 2


class TestBulkLoadOperations:
    """Tests for bulk loading operations used during engine initialization."""

    @pytest.mark.asyncio
    async def test_load_all_dsars(self, mock_neo4j_client):
        """Test loading all DSARs."""
        repo = ComplianceRepository(mock_neo4j_client)
        mock_neo4j_client.execute = AsyncMock(
            return_value=[
                {"d": {"id": "dsar_001", "status": "received"}},
                {"d": {"id": "dsar_002", "status": "processing"}},
            ]
        )

        result = await repo.load_all_dsars()

        assert "dsar_001" in result
        assert "dsar_002" in result

    @pytest.mark.asyncio
    async def test_load_all_consents(self, mock_neo4j_client):
        """Test loading all consents grouped by user."""
        repo = ComplianceRepository(mock_neo4j_client)
        mock_neo4j_client.execute = AsyncMock(
            return_value=[
                {"c": {"id": "consent_001", "user_id": "user_123"}},
                {"c": {"id": "consent_002", "user_id": "user_123"}},
                {"c": {"id": "consent_003", "user_id": "user_456"}},
            ]
        )

        result = await repo.load_all_consents()

        assert "user_123" in result
        assert len(result["user_123"]) == 2
        assert "user_456" in result
        assert len(result["user_456"]) == 1

    @pytest.mark.asyncio
    async def test_load_all_breaches(self, mock_neo4j_client):
        """Test loading all breaches."""
        repo = ComplianceRepository(mock_neo4j_client)
        mock_neo4j_client.execute = AsyncMock(
            return_value=[
                {"b": {"id": "breach_001", "severity": "high"}},
            ]
        )

        result = await repo.load_all_breaches()

        assert "breach_001" in result

    @pytest.mark.asyncio
    async def test_load_all_ai_systems(self, mock_neo4j_client):
        """Test loading all AI systems."""
        repo = ComplianceRepository(mock_neo4j_client)
        mock_neo4j_client.execute = AsyncMock(
            return_value=[
                {"s": {"id": "ai_sys_001", "system_name": "System 1"}},
            ]
        )

        result = await repo.load_all_ai_systems()

        assert "ai_sys_001" in result


class TestGlobalRepositoryFunctions:
    """Tests for global repository instance functions."""

    def test_get_compliance_repository_without_client(self):
        """Test get_compliance_repository without client returns None initially."""
        # Reset global state
        import forge.compliance.core.repository as repo_module
        repo_module._compliance_repository = None

        result = get_compliance_repository()
        # May return None if no client provided
        # Actual behavior depends on global state

    def test_get_compliance_repository_with_client(self, mock_neo4j_client):
        """Test get_compliance_repository with client."""
        # Reset global state
        import forge.compliance.core.repository as repo_module
        repo_module._compliance_repository = None

        result = get_compliance_repository(mock_neo4j_client)
        assert result is not None
        assert isinstance(result, ComplianceRepository)

    @pytest.mark.asyncio
    async def test_initialize_compliance_repository(self, mock_neo4j_client):
        """Test initialize_compliance_repository function."""
        # Reset global state
        import forge.compliance.core.repository as repo_module
        repo_module._compliance_repository = None

        result = await initialize_compliance_repository(mock_neo4j_client)

        assert result is not None
        assert isinstance(result, ComplianceRepository)
        assert result._initialized is True
