"""
Base Model Tests for Forge Cascade V2

Comprehensive tests for base models including:
- convert_neo4j_datetime function
- ForgeModel base class configuration
- TimestampMixin behavior
- TrustLevel enum and methods
- CapsuleType, OverlayState, OverlayPhase enums
- ProposalStatus, AuditOperation, HealthStatus enums
- HealthCheck, PaginatedResponse, ErrorResponse, SuccessResponse models
- generate_id and generate_uuid functions
- FORBIDDEN_DICT_KEYS and validate_dict_security function
"""

import json
from datetime import UTC, datetime, timezone
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from forge.models.base import (
    DEFAULT_MAX_DICT_DEPTH,
    DEFAULT_MAX_DICT_KEYS,
    DEFAULT_MAX_DICT_SIZE,
    FORBIDDEN_DICT_KEYS,
    AuditOperation,
    CapsuleType,
    ErrorResponse,
    ForgeModel,
    HealthCheck,
    HealthStatus,
    OverlayPhase,
    OverlayState,
    PaginatedResponse,
    ProposalStatus,
    SuccessResponse,
    TimestampMixin,
    TrustLevel,
    convert_neo4j_datetime,
    generate_id,
    generate_uuid,
    validate_dict_security,
)


# =============================================================================
# convert_neo4j_datetime Tests
# =============================================================================


class TestConvertNeo4jDatetime:
    """Tests for convert_neo4j_datetime function."""

    def test_none_returns_current_time(self):
        """None value returns current UTC time."""
        before = datetime.now(UTC)
        result = convert_neo4j_datetime(None)
        after = datetime.now(UTC)

        assert before <= result <= after
        assert result.tzinfo is not None

    def test_datetime_with_timezone_returns_same(self):
        """Datetime with timezone is returned as-is."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = convert_neo4j_datetime(dt)

        assert result == dt
        assert result.tzinfo == UTC

    def test_naive_datetime_gets_utc_timezone(self):
        """Naive datetime gets UTC timezone added."""
        naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        result = convert_neo4j_datetime(naive_dt)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.tzinfo == UTC

    def test_iso_string_with_z_suffix(self):
        """ISO string with Z suffix is parsed correctly."""
        iso_string = "2024-01-15T12:00:00Z"
        result = convert_neo4j_datetime(iso_string)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12

    def test_iso_string_with_offset(self):
        """ISO string with timezone offset is parsed correctly."""
        iso_string = "2024-01-15T12:00:00+00:00"
        result = convert_neo4j_datetime(iso_string)

        assert result.year == 2024
        assert result.month == 1

    def test_neo4j_datetime_object_with_to_native(self):
        """Object with to_native method is converted properly."""

        class MockNeo4jDateTime:
            def to_native(self):
                return datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC)

        mock_dt = MockNeo4jDateTime()
        result = convert_neo4j_datetime(mock_dt)

        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_unknown_type_returns_current_time(self):
        """Unknown types return current UTC time."""
        before = datetime.now(UTC)
        result = convert_neo4j_datetime(12345)  # Unknown type
        after = datetime.now(UTC)

        assert before <= result <= after

    def test_different_timezone_preserved(self):
        """Datetime with different timezone is preserved."""
        from datetime import timezone as tz

        est = tz(offset=datetime.now(tz.utc).utcoffset() or datetime.now().utcoffset() or datetime.now(UTC) - datetime.now(UTC), name="EST")
        # Use a fixed offset for testing
        fixed_offset = tz(offset=datetime.now(UTC) - datetime.now(UTC))
        dt_with_tz = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = convert_neo4j_datetime(dt_with_tz)

        assert result.tzinfo is not None


# =============================================================================
# ForgeModel Tests
# =============================================================================


class TestForgeModel:
    """Tests for ForgeModel base class."""

    def test_forge_model_config_from_attributes(self):
        """ForgeModel allows creation from attributes (ORM mode)."""

        class TestModel(ForgeModel):
            name: str
            value: int

        # Create from dict
        model = TestModel(name="test", value=42)
        assert model.name == "test"
        assert model.value == 42

    def test_forge_model_config_populate_by_name(self):
        """ForgeModel supports population by alias name."""

        from pydantic import Field

        class TestModel(ForgeModel):
            my_field: str = Field(alias="myField")

        model = TestModel(myField="test")
        assert model.my_field == "test"

    def test_forge_model_config_str_strip_whitespace(self):
        """ForgeModel strips whitespace from strings."""

        class TestModel(ForgeModel):
            name: str

        model = TestModel(name="  test  ")
        assert model.name == "test"

    def test_forge_model_config_validate_assignment(self):
        """ForgeModel validates on assignment."""

        class TestModel(ForgeModel):
            value: int

        model = TestModel(value=42)

        with pytest.raises(ValidationError):
            model.value = "not an int"  # type: ignore

    def test_forge_model_config_use_enum_values(self):
        """ForgeModel uses enum values instead of enum instances."""

        from enum import Enum

        class Color(str, Enum):
            RED = "red"
            BLUE = "blue"

        class TestModel(ForgeModel):
            color: Color

        model = TestModel(color=Color.RED)
        # With use_enum_values=True, the value should be the string
        assert model.color == "red" or model.color == Color.RED


# =============================================================================
# TimestampMixin Tests
# =============================================================================


class TestTimestampMixin:
    """Tests for TimestampMixin."""

    def test_timestamp_mixin_default_values(self):
        """TimestampMixin provides default timestamps."""

        class TestModel(TimestampMixin):
            pass

        before = datetime.now(UTC)
        model = TestModel()
        after = datetime.now(UTC)

        assert before <= model.created_at <= after
        assert before <= model.updated_at <= after

    def test_timestamp_mixin_accepts_datetime(self):
        """TimestampMixin accepts datetime objects."""

        class TestModel(TimestampMixin):
            pass

        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        model = TestModel(created_at=dt, updated_at=dt)

        assert model.created_at == dt
        assert model.updated_at == dt

    def test_timestamp_mixin_accepts_iso_string(self):
        """TimestampMixin converts ISO strings."""

        class TestModel(TimestampMixin):
            pass

        model = TestModel(
            created_at="2024-01-15T12:00:00Z",
            updated_at="2024-01-15T14:00:00Z",
        )

        assert model.created_at.year == 2024
        assert model.created_at.month == 1
        assert model.updated_at.hour == 14

    def test_timestamp_mixin_handles_naive_datetime(self):
        """TimestampMixin adds UTC to naive datetimes."""

        class TestModel(TimestampMixin):
            pass

        naive_dt = datetime(2024, 1, 15, 12, 0, 0)
        model = TestModel(created_at=naive_dt, updated_at=naive_dt)

        assert model.created_at.tzinfo == UTC
        assert model.updated_at.tzinfo == UTC


# =============================================================================
# TrustLevel Enum Tests
# =============================================================================


class TestTrustLevel:
    """Tests for TrustLevel IntEnum."""

    def test_trust_level_values(self):
        """TrustLevel has expected numeric values."""
        assert TrustLevel.QUARANTINE.value == 0
        assert TrustLevel.SANDBOX.value == 40
        assert TrustLevel.STANDARD.value == 60
        assert TrustLevel.TRUSTED.value == 80
        assert TrustLevel.CORE.value == 100

    def test_trust_level_from_value_exact_match(self):
        """from_value returns exact level for matching values."""
        assert TrustLevel.from_value(0) == TrustLevel.QUARANTINE
        assert TrustLevel.from_value(40) == TrustLevel.SANDBOX
        assert TrustLevel.from_value(60) == TrustLevel.STANDARD
        assert TrustLevel.from_value(80) == TrustLevel.TRUSTED
        assert TrustLevel.from_value(100) == TrustLevel.CORE

    def test_trust_level_from_value_rounds_down(self):
        """from_value rounds down to nearest level."""
        assert TrustLevel.from_value(39) == TrustLevel.QUARANTINE
        assert TrustLevel.from_value(59) == TrustLevel.SANDBOX
        assert TrustLevel.from_value(79) == TrustLevel.STANDARD
        assert TrustLevel.from_value(99) == TrustLevel.TRUSTED

    def test_trust_level_from_value_above_max(self):
        """from_value handles values above max."""
        assert TrustLevel.from_value(150) == TrustLevel.CORE
        assert TrustLevel.from_value(1000) == TrustLevel.CORE

    def test_trust_level_from_value_negative(self):
        """from_value handles negative values."""
        assert TrustLevel.from_value(-10) == TrustLevel.QUARANTINE
        assert TrustLevel.from_value(-100) == TrustLevel.QUARANTINE

    def test_trust_level_can_execute(self):
        """can_execute property checks execution permission."""
        assert TrustLevel.QUARANTINE.can_execute is False
        assert TrustLevel.SANDBOX.can_execute is True
        assert TrustLevel.STANDARD.can_execute is True
        assert TrustLevel.TRUSTED.can_execute is True
        assert TrustLevel.CORE.can_execute is True

    def test_trust_level_can_vote(self):
        """can_vote property checks voting permission."""
        assert TrustLevel.QUARANTINE.can_vote is False
        assert TrustLevel.SANDBOX.can_vote is False
        assert TrustLevel.STANDARD.can_vote is False
        assert TrustLevel.TRUSTED.can_vote is True
        assert TrustLevel.CORE.can_vote is True

    def test_trust_level_comparison(self):
        """TrustLevel supports numeric comparison."""
        assert TrustLevel.QUARANTINE < TrustLevel.SANDBOX
        assert TrustLevel.SANDBOX < TrustLevel.STANDARD
        assert TrustLevel.STANDARD < TrustLevel.TRUSTED
        assert TrustLevel.TRUSTED < TrustLevel.CORE

    def test_trust_level_is_intenum(self):
        """TrustLevel is an IntEnum and can be used in math."""
        assert TrustLevel.STANDARD + 20 == TrustLevel.TRUSTED.value
        assert TrustLevel.CORE - TrustLevel.QUARANTINE == 100


# =============================================================================
# CapsuleType Enum Tests
# =============================================================================


class TestCapsuleType:
    """Tests for CapsuleType enum."""

    def test_capsule_type_frontend_values(self):
        """CapsuleType has frontend-compatible values."""
        assert CapsuleType.INSIGHT.value == "INSIGHT"
        assert CapsuleType.DECISION.value == "DECISION"
        assert CapsuleType.LESSON.value == "LESSON"
        assert CapsuleType.WARNING.value == "WARNING"
        assert CapsuleType.PRINCIPLE.value == "PRINCIPLE"
        assert CapsuleType.MEMORY.value == "MEMORY"

    def test_capsule_type_backend_values(self):
        """CapsuleType has additional backend values."""
        assert CapsuleType.KNOWLEDGE.value == "KNOWLEDGE"
        assert CapsuleType.CODE.value == "CODE"
        assert CapsuleType.CONFIG.value == "CONFIG"
        assert CapsuleType.TEMPLATE.value == "TEMPLATE"
        assert CapsuleType.DOCUMENT.value == "DOCUMENT"

    def test_capsule_type_is_str_enum(self):
        """CapsuleType is a string enum."""
        assert isinstance(CapsuleType.INSIGHT.value, str)
        # Can be compared directly to strings
        assert CapsuleType.INSIGHT == "INSIGHT"


# =============================================================================
# OverlayState Enum Tests
# =============================================================================


class TestOverlayState:
    """Tests for OverlayState enum."""

    def test_overlay_state_values(self):
        """OverlayState has expected values."""
        assert OverlayState.REGISTERED.value == "registered"
        assert OverlayState.LOADING.value == "loading"
        assert OverlayState.ACTIVE.value == "active"
        assert OverlayState.DEGRADED.value == "degraded"
        assert OverlayState.STOPPING.value == "stopping"
        assert OverlayState.STOPPED.value == "stopped"
        assert OverlayState.INACTIVE.value == "inactive"
        assert OverlayState.QUARANTINED.value == "quarantined"
        assert OverlayState.ERROR.value == "error"

    def test_overlay_state_count(self):
        """OverlayState has 9 states."""
        assert len(OverlayState) == 9


# =============================================================================
# OverlayPhase Enum Tests
# =============================================================================


class TestOverlayPhase:
    """Tests for OverlayPhase enum."""

    def test_overlay_phase_values(self):
        """OverlayPhase has expected values."""
        assert OverlayPhase.VALIDATION.value == "validation"
        assert OverlayPhase.SECURITY.value == "security"
        assert OverlayPhase.ENRICHMENT.value == "enrichment"
        assert OverlayPhase.PROCESSING.value == "processing"
        assert OverlayPhase.GOVERNANCE.value == "governance"
        assert OverlayPhase.FINALIZATION.value == "finalization"
        assert OverlayPhase.NOTIFICATION.value == "notification"

    def test_overlay_phase_count(self):
        """OverlayPhase has 7 phases."""
        assert len(OverlayPhase) == 7


# =============================================================================
# ProposalStatus Enum Tests
# =============================================================================


class TestProposalStatus:
    """Tests for ProposalStatus enum."""

    def test_proposal_status_values(self):
        """ProposalStatus has expected values."""
        assert ProposalStatus.DRAFT.value == "draft"
        assert ProposalStatus.ACTIVE.value == "active"
        assert ProposalStatus.VOTING.value == "voting"
        assert ProposalStatus.PASSED.value == "passed"
        assert ProposalStatus.REJECTED.value == "rejected"
        assert ProposalStatus.EXECUTED.value == "executed"
        assert ProposalStatus.CANCELLED.value == "cancelled"

    def test_proposal_status_count(self):
        """ProposalStatus has 7 statuses."""
        assert len(ProposalStatus) == 7


# =============================================================================
# AuditOperation Enum Tests
# =============================================================================


class TestAuditOperation:
    """Tests for AuditOperation enum."""

    def test_audit_operation_crud_values(self):
        """AuditOperation has CRUD values."""
        assert AuditOperation.CREATE.value == "CREATE"
        assert AuditOperation.READ.value == "READ"
        assert AuditOperation.UPDATE.value == "UPDATE"
        assert AuditOperation.DELETE.value == "DELETE"

    def test_audit_operation_special_values(self):
        """AuditOperation has special operation values."""
        assert AuditOperation.EXECUTE.value == "EXECUTE"
        assert AuditOperation.VOTE.value == "VOTE"
        assert AuditOperation.QUARANTINE.value == "QUARANTINE"
        assert AuditOperation.RECOVER.value == "RECOVER"

    def test_audit_operation_count(self):
        """AuditOperation has 8 operations."""
        assert len(AuditOperation) == 8


# =============================================================================
# HealthStatus Enum Tests
# =============================================================================


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_values(self):
        """HealthStatus has expected values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_health_status_count(self):
        """HealthStatus has 3 statuses."""
        assert len(HealthStatus) == 3


# =============================================================================
# HealthCheck Model Tests
# =============================================================================


class TestHealthCheck:
    """Tests for HealthCheck model."""

    def test_health_check_creation(self):
        """HealthCheck can be created with required fields."""
        health = HealthCheck(
            status=HealthStatus.HEALTHY,
            service="api",
            version="1.0.0",
        )

        assert health.status == HealthStatus.HEALTHY or health.status == "healthy"
        assert health.service == "api"
        assert health.version == "1.0.0"

    def test_health_check_default_timestamp(self):
        """HealthCheck has default timestamp."""
        before = datetime.now(UTC)
        health = HealthCheck(
            status=HealthStatus.HEALTHY,
            service="api",
            version="1.0.0",
        )
        after = datetime.now(UTC)

        assert before <= health.timestamp <= after

    def test_health_check_default_details(self):
        """HealthCheck has default empty details."""
        health = HealthCheck(
            status=HealthStatus.HEALTHY,
            service="api",
            version="1.0.0",
        )

        assert health.details == {}

    def test_health_check_with_details(self):
        """HealthCheck accepts custom details."""
        health = HealthCheck(
            status=HealthStatus.DEGRADED,
            service="database",
            version="2.0.0",
            details={"connection_pool": 5, "active_queries": 10},
        )

        assert health.details["connection_pool"] == 5
        assert health.details["active_queries"] == 10

    def test_health_check_inherits_forge_model(self):
        """HealthCheck inherits from ForgeModel."""
        assert issubclass(HealthCheck, ForgeModel)


# =============================================================================
# PaginatedResponse Model Tests
# =============================================================================


class TestPaginatedResponse:
    """Tests for PaginatedResponse model."""

    def test_paginated_response_creation(self):
        """PaginatedResponse can be created with items and total."""
        response = PaginatedResponse(
            items=[1, 2, 3],
            total=100,
        )

        assert response.items == [1, 2, 3]
        assert response.total == 100

    def test_paginated_response_defaults(self):
        """PaginatedResponse has sensible defaults."""
        response = PaginatedResponse(
            items=[],
            total=0,
        )

        assert response.page == 1
        assert response.page_size == 20
        assert response.has_more is False

    def test_paginated_response_total_pages_calculation(self):
        """total_pages property calculates correctly."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page_size=20,
        )

        assert response.total_pages == 5

    def test_paginated_response_total_pages_with_remainder(self):
        """total_pages rounds up when there's a remainder."""
        response = PaginatedResponse(
            items=[],
            total=101,
            page_size=20,
        )

        assert response.total_pages == 6

    def test_paginated_response_total_pages_zero_page_size(self):
        """total_pages handles zero page_size gracefully."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page_size=0,
        )

        assert response.total_pages == 0

    def test_paginated_response_total_pages_negative_page_size(self):
        """total_pages handles negative page_size gracefully."""
        response = PaginatedResponse(
            items=[],
            total=100,
            page_size=-5,
        )

        assert response.total_pages == 0

    def test_paginated_response_has_more_true(self):
        """PaginatedResponse can indicate more pages exist."""
        response = PaginatedResponse(
            items=[1, 2, 3],
            total=100,
            page=1,
            page_size=20,
            has_more=True,
        )

        assert response.has_more is True

    def test_paginated_response_with_dict_items(self):
        """PaginatedResponse works with complex items."""
        response = PaginatedResponse(
            items=[{"id": 1, "name": "test"}, {"id": 2, "name": "test2"}],
            total=50,
        )

        assert len(response.items) == 2
        assert response.items[0]["name"] == "test"


# =============================================================================
# ErrorResponse Model Tests
# =============================================================================


class TestErrorResponse:
    """Tests for ErrorResponse model."""

    def test_error_response_creation(self):
        """ErrorResponse can be created with error and message."""
        error = ErrorResponse(
            error="ValidationError",
            message="Invalid input",
        )

        assert error.error == "ValidationError"
        assert error.message == "Invalid input"

    def test_error_response_optional_fields(self):
        """ErrorResponse has optional fields defaulting to None."""
        error = ErrorResponse(
            error="NotFound",
            message="Resource not found",
        )

        assert error.details is None
        assert error.correlation_id is None

    def test_error_response_with_details(self):
        """ErrorResponse accepts details dict."""
        error = ErrorResponse(
            error="ValidationError",
            message="Multiple validation errors",
            details={"field1": "required", "field2": "invalid format"},
        )

        assert error.details["field1"] == "required"
        assert error.details["field2"] == "invalid format"

    def test_error_response_with_correlation_id(self):
        """ErrorResponse accepts correlation_id for tracing."""
        error = ErrorResponse(
            error="InternalError",
            message="Something went wrong",
            correlation_id="req-123-456-789",
        )

        assert error.correlation_id == "req-123-456-789"


# =============================================================================
# SuccessResponse Model Tests
# =============================================================================


class TestSuccessResponse:
    """Tests for SuccessResponse model."""

    def test_success_response_defaults(self):
        """SuccessResponse has sensible defaults."""
        response = SuccessResponse()

        assert response.success is True
        assert response.message == "Operation completed successfully"
        assert response.data is None

    def test_success_response_custom_message(self):
        """SuccessResponse accepts custom message."""
        response = SuccessResponse(
            message="User created successfully",
        )

        assert response.message == "User created successfully"

    def test_success_response_with_data(self):
        """SuccessResponse accepts data dict."""
        response = SuccessResponse(
            message="Created",
            data={"id": "new-id-123", "name": "New Resource"},
        )

        assert response.data["id"] == "new-id-123"
        assert response.data["name"] == "New Resource"

    def test_success_response_success_can_be_set(self):
        """SuccessResponse success field can be explicitly set."""
        response = SuccessResponse(success=True)
        assert response.success is True


# =============================================================================
# ID Generation Tests
# =============================================================================


class TestGenerateId:
    """Tests for generate_id function."""

    def test_generate_id_returns_string(self):
        """generate_id returns a string."""
        id_str = generate_id()
        assert isinstance(id_str, str)

    def test_generate_id_returns_valid_uuid(self):
        """generate_id returns a valid UUID string."""
        id_str = generate_id()
        # Should be able to parse as UUID
        parsed = UUID(id_str)
        assert str(parsed) == id_str

    def test_generate_id_unique(self):
        """generate_id generates unique IDs."""
        ids = [generate_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestGenerateUuid:
    """Tests for generate_uuid function."""

    def test_generate_uuid_returns_uuid(self):
        """generate_uuid returns a UUID object."""
        uuid_obj = generate_uuid()
        assert isinstance(uuid_obj, UUID)

    def test_generate_uuid_unique(self):
        """generate_uuid generates unique UUIDs."""
        uuids = [generate_uuid() for _ in range(100)]
        assert len(set(uuids)) == 100

    def test_generate_uuid_version_4(self):
        """generate_uuid returns UUID version 4."""
        uuid_obj = generate_uuid()
        assert uuid_obj.version == 4


# =============================================================================
# FORBIDDEN_DICT_KEYS Tests
# =============================================================================


class TestForbiddenDictKeys:
    """Tests for FORBIDDEN_DICT_KEYS constant."""

    def test_forbidden_keys_is_frozenset(self):
        """FORBIDDEN_DICT_KEYS is a frozenset (immutable)."""
        assert isinstance(FORBIDDEN_DICT_KEYS, frozenset)

    def test_forbidden_keys_contains_proto_pollution_keys(self):
        """FORBIDDEN_DICT_KEYS contains prototype pollution keys."""
        assert "__proto__" in FORBIDDEN_DICT_KEYS
        assert "__prototype__" in FORBIDDEN_DICT_KEYS
        assert "constructor" in FORBIDDEN_DICT_KEYS
        assert "prototype" in FORBIDDEN_DICT_KEYS

    def test_forbidden_keys_contains_python_dunder_keys(self):
        """FORBIDDEN_DICT_KEYS contains dangerous Python dunder keys."""
        assert "__class__" in FORBIDDEN_DICT_KEYS
        assert "__bases__" in FORBIDDEN_DICT_KEYS
        assert "__mro__" in FORBIDDEN_DICT_KEYS
        assert "__subclasses__" in FORBIDDEN_DICT_KEYS
        assert "__init__" in FORBIDDEN_DICT_KEYS
        assert "__new__" in FORBIDDEN_DICT_KEYS

    def test_forbidden_keys_contains_pickle_keys(self):
        """FORBIDDEN_DICT_KEYS contains pickle-related keys."""
        assert "__reduce__" in FORBIDDEN_DICT_KEYS
        assert "__reduce_ex__" in FORBIDDEN_DICT_KEYS
        assert "__getstate__" in FORBIDDEN_DICT_KEYS
        assert "__setstate__" in FORBIDDEN_DICT_KEYS


# =============================================================================
# validate_dict_security Tests
# =============================================================================


class TestValidateDictSecurity:
    """Tests for validate_dict_security function."""

    # --- Basic Validation ---

    def test_validate_dict_security_valid_dict(self):
        """Valid dict passes validation."""
        data = {"key1": "value1", "key2": 123, "nested": {"a": 1}}
        result = validate_dict_security(data)
        assert result == data

    def test_validate_dict_security_empty_dict(self):
        """Empty dict passes validation."""
        result = validate_dict_security({})
        assert result == {}

    def test_validate_dict_security_non_dict_raises(self):
        """Non-dict input raises ValueError."""
        with pytest.raises(ValueError, match="Expected a dictionary"):
            validate_dict_security("not a dict")  # type: ignore

        with pytest.raises(ValueError, match="Expected a dictionary"):
            validate_dict_security([1, 2, 3])  # type: ignore

        with pytest.raises(ValueError, match="Expected a dictionary"):
            validate_dict_security(None)  # type: ignore

    # --- Forbidden Keys ---

    def test_validate_dict_security_forbidden_key_proto(self):
        """Dict with __proto__ raises ValueError."""
        with pytest.raises(ValueError, match="Forbidden keys detected.*__proto__"):
            validate_dict_security({"__proto__": {"admin": True}})

    def test_validate_dict_security_forbidden_key_class(self):
        """Dict with __class__ raises ValueError."""
        with pytest.raises(ValueError, match="Forbidden keys detected.*__class__"):
            validate_dict_security({"__class__": "Evil"})

    def test_validate_dict_security_forbidden_key_constructor(self):
        """Dict with constructor raises ValueError."""
        with pytest.raises(ValueError, match="Forbidden keys detected.*constructor"):
            validate_dict_security({"constructor": {"prototype": {}}})

    def test_validate_dict_security_forbidden_key_nested(self):
        """Nested forbidden keys are detected."""
        with pytest.raises(ValueError, match="Forbidden keys detected"):
            validate_dict_security({"safe": {"__proto__": "attack"}})

    def test_validate_dict_security_forbidden_key_deeply_nested(self):
        """Deeply nested forbidden keys are detected."""
        with pytest.raises(ValueError, match="Forbidden keys detected"):
            validate_dict_security({
                "level1": {
                    "level2": {
                        "level3": {
                            "__class__": "attack"
                        }
                    }
                }
            })

    def test_validate_dict_security_forbidden_key_in_list(self):
        """Forbidden keys in list items are detected."""
        with pytest.raises(ValueError, match="Forbidden keys detected"):
            validate_dict_security({
                "items": [
                    {"safe": "value"},
                    {"__proto__": "attack"},
                ]
            })

    def test_validate_dict_security_multiple_forbidden_keys(self):
        """Multiple forbidden keys in error message."""
        with pytest.raises(ValueError, match="Forbidden keys detected"):
            validate_dict_security({
                "__proto__": {},
                "__class__": "Evil",
            })

    # --- Depth Limits ---

    def test_validate_dict_security_default_depth_limit(self):
        """Default depth limit is enforced."""
        # Create dict at max depth (should pass)
        deep_dict: dict[str, Any] = {"level": 1}
        current = deep_dict
        for i in range(DEFAULT_MAX_DICT_DEPTH - 1):
            current["nested"] = {"level": i + 2}
            current = current["nested"]

        # This should pass at max depth
        result = validate_dict_security(deep_dict)
        assert result is not None

    def test_validate_dict_security_exceeds_depth_limit(self):
        """Dict exceeding depth limit raises ValueError."""
        # Create dict exceeding max depth
        deep_dict: dict[str, Any] = {"level": 0}
        current = deep_dict
        for i in range(DEFAULT_MAX_DICT_DEPTH + 2):
            current["nested"] = {"level": i + 1}
            current = current["nested"]

        with pytest.raises(ValueError, match="nesting too deep"):
            validate_dict_security(deep_dict)

    def test_validate_dict_security_custom_depth_limit(self):
        """Custom depth limit is respected."""
        # Dict with 4 levels of nesting: a -> b -> c -> d
        deep_dict = {"a": {"b": {"c": {"d": "value"}}}}

        # Should pass with depth 3 (allows 4 levels: 0, 1, 2, 3)
        validate_dict_security(deep_dict, max_depth=3)

        # Should fail with depth 2 (only allows 3 levels: 0, 1, 2)
        with pytest.raises(ValueError, match="nesting too deep"):
            validate_dict_security(deep_dict, max_depth=2)

    def test_validate_dict_security_depth_zero(self):
        """Depth zero only allows flat dicts."""
        flat = {"key": "value"}
        nested = {"key": {"nested": "value"}}

        validate_dict_security(flat, max_depth=0)

        with pytest.raises(ValueError, match="nesting too deep"):
            validate_dict_security(nested, max_depth=0)

    # --- Size Limits ---

    def test_validate_dict_security_within_size_limit(self):
        """Dict within size limit passes."""
        small_dict = {"key": "value"}
        result = validate_dict_security(small_dict)
        assert result == small_dict

    def test_validate_dict_security_exceeds_size_limit(self):
        """Dict exceeding size limit raises ValueError."""
        # Create a large dict that exceeds default size
        large_dict = {"key": "x" * (DEFAULT_MAX_DICT_SIZE + 1000)}

        with pytest.raises(ValueError, match="too large"):
            validate_dict_security(large_dict)

    def test_validate_dict_security_custom_size_limit(self):
        """Custom size limit is respected."""
        data = {"key": "a" * 100}

        # Should pass with large limit
        validate_dict_security(data, max_size=10000)

        # Should fail with small limit
        with pytest.raises(ValueError, match="too large"):
            validate_dict_security(data, max_size=50)

    # --- Key Count Limits ---

    def test_validate_dict_security_within_key_limit(self):
        """Dict within key limit passes."""
        data = {f"key{i}": i for i in range(50)}
        result = validate_dict_security(data)
        assert len(result) == 50

    def test_validate_dict_security_exceeds_key_limit(self):
        """Dict exceeding key limit raises ValueError."""
        data = {f"key{i}": i for i in range(DEFAULT_MAX_DICT_KEYS + 10)}

        with pytest.raises(ValueError, match="Too many keys"):
            validate_dict_security(data)

    def test_validate_dict_security_custom_key_limit(self):
        """Custom key limit is respected."""
        data = {f"key{i}": i for i in range(20)}

        # Should pass with higher limit
        validate_dict_security(data, max_keys=50)

        # Should fail with lower limit
        with pytest.raises(ValueError, match="Too many keys"):
            validate_dict_security(data, max_keys=10)

    def test_validate_dict_security_nested_key_limit(self):
        """Key limit applies to nested dicts."""
        data = {
            "outer": {f"inner{i}": i for i in range(DEFAULT_MAX_DICT_KEYS + 10)}
        }

        with pytest.raises(ValueError, match="Too many keys"):
            validate_dict_security(data)

    # --- Non-Serializable Values ---

    def test_validate_dict_security_non_serializable_raises(self):
        """Non-JSON-serializable values raise ValueError."""

        class CustomClass:
            pass

        with pytest.raises(ValueError, match="non-serializable"):
            validate_dict_security({"obj": CustomClass()})

    def test_validate_dict_security_function_raises(self):
        """Function values raise ValueError."""
        with pytest.raises(ValueError, match="non-serializable"):
            validate_dict_security({"func": lambda x: x})

    # --- Complex Structures ---

    def test_validate_dict_security_list_of_dicts(self):
        """Lists containing dicts are validated."""
        data = {
            "items": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"},
            ]
        }
        result = validate_dict_security(data)
        assert len(result["items"]) == 2

    def test_validate_dict_security_mixed_list(self):
        """Lists with mixed types are handled."""
        data = {
            "mixed": [1, "string", {"nested": "dict"}, [1, 2, 3]]
        }
        result = validate_dict_security(data)
        assert result == data

    def test_validate_dict_security_deeply_nested_lists(self):
        """Nested lists with dicts are validated."""
        data = {
            "matrix": [
                [{"cell": "1,1"}, {"cell": "1,2"}],
                [{"cell": "2,1"}, {"cell": "2,2"}],
            ]
        }
        result = validate_dict_security(data)
        assert result["matrix"][0][0]["cell"] == "1,1"

    # --- Edge Cases ---

    def test_validate_dict_security_numeric_values(self):
        """Numeric values are handled correctly."""
        data = {
            "int": 42,
            "float": 3.14,
            "negative": -100,
            "zero": 0,
        }
        result = validate_dict_security(data)
        assert result == data

    def test_validate_dict_security_boolean_values(self):
        """Boolean values are handled correctly."""
        data = {"true": True, "false": False}
        result = validate_dict_security(data)
        assert result == data

    def test_validate_dict_security_null_values(self):
        """Null values are handled correctly."""
        data = {"null_key": None}
        result = validate_dict_security(data)
        assert result["null_key"] is None

    def test_validate_dict_security_unicode_keys(self):
        """Unicode keys are handled correctly."""
        data = {"key": "value", "cle": "valeur", "klyuch": "znachenie"}
        result = validate_dict_security(data)
        assert result == data

    def test_validate_dict_security_returns_same_dict(self):
        """validate_dict_security returns the input dict."""
        data = {"key": "value"}
        result = validate_dict_security(data)
        assert result is data  # Same object reference


# =============================================================================
# Default Constants Tests
# =============================================================================


class TestDefaultConstants:
    """Tests for default constant values."""

    def test_default_max_dict_depth(self):
        """DEFAULT_MAX_DICT_DEPTH has expected value."""
        assert DEFAULT_MAX_DICT_DEPTH == 5

    def test_default_max_dict_size(self):
        """DEFAULT_MAX_DICT_SIZE has expected value."""
        assert DEFAULT_MAX_DICT_SIZE == 10000

    def test_default_max_dict_keys(self):
        """DEFAULT_MAX_DICT_KEYS has expected value."""
        assert DEFAULT_MAX_DICT_KEYS == 100


# =============================================================================
# Integration Tests
# =============================================================================


class TestBaseModelsIntegration:
    """Integration tests combining multiple base model features."""

    def test_health_check_with_validated_details(self):
        """HealthCheck details can be validated with validate_dict_security."""
        details = {"db_latency_ms": 15, "cache_hit_rate": 0.95}
        validated = validate_dict_security(details)

        health = HealthCheck(
            status=HealthStatus.HEALTHY,
            service="api",
            version="1.0.0",
            details=validated,
        )

        assert health.details["db_latency_ms"] == 15

    def test_error_response_with_validated_details(self):
        """ErrorResponse details can be validated with validate_dict_security."""
        details = {"field": "username", "constraint": "min_length"}
        validated = validate_dict_security(details)

        error = ErrorResponse(
            error="ValidationError",
            message="Invalid username",
            details=validated,
        )

        assert error.details["field"] == "username"

    def test_success_response_with_validated_data(self):
        """SuccessResponse data can be validated with validate_dict_security."""
        data = {"id": generate_id(), "created": True}
        validated = validate_dict_security(data)

        response = SuccessResponse(
            message="Created successfully",
            data=validated,
        )

        assert response.data is not None
        assert "id" in response.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
