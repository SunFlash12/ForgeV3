"""
Tests for Content Validation Pipeline
======================================

Tests for forge/resilience/security/content_validator.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge.resilience.security.content_validator import (
    ContentPattern,
    ContentValidator,
    ThreatLevel,
    ValidationIssue,
    ValidationResult,
    ValidationStage,
    get_content_validator,
    validate_content,
)


class TestThreatLevel:
    """Tests for ThreatLevel enum."""

    def test_threat_level_values(self):
        """Test all threat level values."""
        assert ThreatLevel.NONE.value == "none"
        assert ThreatLevel.LOW.value == "low"
        assert ThreatLevel.MEDIUM.value == "medium"
        assert ThreatLevel.HIGH.value == "high"
        assert ThreatLevel.CRITICAL.value == "critical"


class TestValidationStage:
    """Tests for ValidationStage enum."""

    def test_stage_values(self):
        """Test all validation stage values."""
        assert ValidationStage.INPUT_SANITIZATION.value == "input_sanitization"
        assert ValidationStage.PATTERN_MATCHING.value == "pattern_matching"
        assert ValidationStage.ANOMALY_DETECTION.value == "anomaly_detection"
        assert ValidationStage.ML_CLASSIFICATION.value == "ml_classification"
        assert ValidationStage.POLICY_CHECK.value == "policy_check"


class TestValidationIssue:
    """Tests for ValidationIssue dataclass."""

    def test_issue_creation(self):
        """Test creating a validation issue."""
        issue = ValidationIssue(
            stage=ValidationStage.PATTERN_MATCHING,
            severity=ThreatLevel.HIGH,
            message="SQL injection attempt detected",
            pattern="sql_injection",
            location="line 5",
        )

        assert issue.stage == ValidationStage.PATTERN_MATCHING
        assert issue.severity == ThreatLevel.HIGH
        assert issue.message == "SQL injection attempt detected"
        assert issue.pattern == "sql_injection"
        assert issue.location == "line 5"


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_result_defaults(self):
        """Test default result values."""
        result = ValidationResult(
            valid=True,
            threat_level=ThreatLevel.NONE,
        )

        assert result.valid is True
        assert result.threat_level == ThreatLevel.NONE
        assert result.issues == []
        assert result.sanitized_content is None
        assert result.processing_time_ms == 0.0

    def test_add_issue(self):
        """Test adding issue to result."""
        result = ValidationResult(
            valid=True,
            threat_level=ThreatLevel.NONE,
        )

        issue = ValidationIssue(
            stage=ValidationStage.PATTERN_MATCHING,
            severity=ThreatLevel.MEDIUM,
            message="Potential issue",
        )

        result.add_issue(issue)

        assert len(result.issues) == 1
        assert result.threat_level == ThreatLevel.MEDIUM

    def test_add_issue_updates_threat_level(self):
        """Test that adding issue updates threat level to highest."""
        result = ValidationResult(
            valid=True,
            threat_level=ThreatLevel.LOW,
        )

        result.add_issue(
            ValidationIssue(
                stage=ValidationStage.PATTERN_MATCHING,
                severity=ThreatLevel.HIGH,
                message="High severity issue",
            )
        )

        assert result.threat_level == ThreatLevel.HIGH

        # Adding lower severity doesn't lower the level
        result.add_issue(
            ValidationIssue(
                stage=ValidationStage.ANOMALY_DETECTION,
                severity=ThreatLevel.LOW,
                message="Low severity issue",
            )
        )

        assert result.threat_level == ThreatLevel.HIGH


class TestContentPattern:
    """Tests for ContentPattern dataclass."""

    def test_pattern_creation(self):
        """Test creating a content pattern."""
        pattern = ContentPattern(
            name="test_pattern",
            pattern=r"\btest\b",
            severity=ThreatLevel.LOW,
            description="Test pattern",
        )

        assert pattern.name == "test_pattern"
        assert pattern.pattern == r"\btest\b"
        assert pattern.severity == ThreatLevel.LOW
        assert pattern.enabled is True


class TestContentValidator:
    """Tests for ContentValidator class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock config."""
        config = MagicMock()
        config.enabled = True
        config.anomaly_threshold = 0.8
        config.max_content_length = 1000000
        config.enable_ml_classification = False
        config.quarantine_on_threat = True
        config.log_threats = True
        return config

    @pytest.fixture
    def validator(self, mock_config):
        """Create a validator instance."""
        with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
            mock.return_value.content_validation = mock_config
            v = ContentValidator()
            v.initialize()
            return v

    def test_validator_creation(self, mock_config):
        """Test validator creation."""
        with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
            mock.return_value.content_validation = mock_config
            validator = ContentValidator()

            assert validator._initialized is False
            assert validator._patterns == []

    def test_initialize(self, validator):
        """Test validator initialization."""
        assert validator._initialized is True
        assert len(validator._patterns) > 0

    def test_initialize_idempotent(self, validator):
        """Test that initialize is idempotent."""
        initial_count = len(validator._patterns)
        validator.initialize()
        assert len(validator._patterns) == initial_count

    def test_add_pattern(self, validator):
        """Test adding custom pattern."""
        pattern = ContentPattern(
            name="custom",
            pattern=r"custom_bad_word",
            severity=ThreatLevel.MEDIUM,
            description="Custom pattern",
        )

        validator.add_pattern(pattern)

        assert pattern in validator._patterns

    def test_add_validator(self, validator):
        """Test adding custom validator."""
        def custom_validator(content):
            if "forbidden" in content:
                return ValidationIssue(
                    stage=ValidationStage.POLICY_CHECK,
                    severity=ThreatLevel.MEDIUM,
                    message="Forbidden word detected",
                )
            return None

        validator.add_validator(custom_validator)

        assert custom_validator in validator._custom_validators

    @pytest.mark.asyncio
    async def test_validate_clean_content(self, validator):
        """Test validating clean content."""
        result = await validator.validate("This is clean content.")

        assert result.valid is True
        assert result.threat_level == ThreatLevel.NONE

    @pytest.mark.asyncio
    async def test_validate_disabled(self, mock_config):
        """Test validation when disabled."""
        mock_config.enabled = False

        with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
            mock.return_value.content_validation = mock_config
            validator = ContentValidator()
            validator.initialize()

            result = await validator.validate("SELECT * FROM users; DROP TABLE users;")

            assert result.valid is True

    @pytest.mark.asyncio
    async def test_validate_content_too_long(self, mock_config):
        """Test validation of content exceeding max length."""
        mock_config.max_content_length = 100

        with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
            mock.return_value.content_validation = mock_config
            validator = ContentValidator()
            validator.initialize()

            long_content = "x" * 200
            result = await validator.validate(long_content)

            assert result.valid is False
            assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_validate_sql_injection(self, validator):
        """Test detecting SQL injection."""
        content = "SELECT * FROM users WHERE id = 1; DROP TABLE users;"
        result = await validator.validate(content)

        assert result.threat_level.value >= ThreatLevel.MEDIUM.value
        # SQL injection pattern should be detected
        sql_issues = [i for i in result.issues if "sql" in i.message.lower() or "sql" in (i.pattern or "").lower()]
        assert len(sql_issues) > 0 or result.threat_level != ThreatLevel.NONE

    @pytest.mark.asyncio
    async def test_validate_xss_script(self, validator):
        """Test detecting XSS script injection."""
        content = '<script>alert("XSS")</script>'
        result = await validator.validate(content)

        assert result.threat_level.value >= ThreatLevel.MEDIUM.value

    @pytest.mark.asyncio
    async def test_validate_path_traversal(self, validator):
        """Test detecting path traversal."""
        content = "Loading file: ../../../etc/passwd"
        result = await validator.validate(content)

        assert result.threat_level.value >= ThreatLevel.MEDIUM.value

    @pytest.mark.asyncio
    async def test_validate_private_key(self, validator):
        """Test detecting private key exposure."""
        content = """
        -----BEGIN RSA PRIVATE KEY-----
        MIIEpAIBAAKCAQEA...
        -----END RSA PRIVATE KEY-----
        """
        result = await validator.validate(content)

        assert result.threat_level == ThreatLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_sanitize_null_bytes(self, validator):
        """Test that null bytes are removed."""
        content = "Hello\x00World"
        result = await validator.validate(content)

        assert "\x00" not in result.sanitized_content
        # Should have issue about null bytes
        null_issues = [i for i in result.issues if "null" in i.message.lower()]
        assert len(null_issues) > 0

    @pytest.mark.asyncio
    async def test_sanitize_control_characters(self, validator):
        """Test that control characters are removed."""
        content = "Hello\x07World\x08"
        result = await validator.validate(content)

        assert "\x07" not in result.sanitized_content
        assert "\x08" not in result.sanitized_content

    @pytest.mark.asyncio
    async def test_anomaly_high_special_chars(self, mock_config):
        """Test anomaly detection for high special character ratio."""
        mock_config.anomaly_threshold = 0.3

        with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
            mock.return_value.content_validation = mock_config
            validator = ContentValidator()
            validator.initialize()

            content = "!!@@##$$%%^^&&**(())"  # All special chars
            result = await validator.validate(content)

            anomaly_issues = [i for i in result.issues if i.stage == ValidationStage.ANOMALY_DETECTION]
            assert len(anomaly_issues) > 0

    @pytest.mark.asyncio
    async def test_custom_validator_called(self, validator):
        """Test that custom validators are called."""
        def custom_validator(content):
            if "forbidden" in content:
                return ValidationIssue(
                    stage=ValidationStage.POLICY_CHECK,
                    severity=ThreatLevel.MEDIUM,
                    message="Forbidden word detected",
                )
            return None

        validator.add_validator(custom_validator)

        result = await validator.validate("This contains forbidden content.")

        custom_issues = [i for i in result.issues if i.stage == ValidationStage.POLICY_CHECK]
        assert len(custom_issues) > 0

    @pytest.mark.asyncio
    async def test_custom_async_validator(self, validator):
        """Test async custom validator."""
        async def async_validator(content):
            await asyncio.sleep(0.01)
            if "async_forbidden" in content:
                return ValidationIssue(
                    stage=ValidationStage.POLICY_CHECK,
                    severity=ThreatLevel.MEDIUM,
                    message="Async forbidden detected",
                )
            return None

        validator.add_validator(async_validator)

        result = await validator.validate("This contains async_forbidden content.")

        custom_issues = [i for i in result.issues if "async" in i.message.lower()]
        assert len(custom_issues) > 0

    @pytest.mark.asyncio
    async def test_quarantine_on_high_threat(self, mock_config):
        """Test quarantine metadata on high threat."""
        mock_config.quarantine_on_threat = True

        with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
            mock.return_value.content_validation = mock_config
            validator = ContentValidator()
            validator.initialize()

            content = "-----BEGIN RSA PRIVATE KEY-----"
            result = await validator.validate(content)

            if result.threat_level in (ThreatLevel.HIGH, ThreatLevel.CRITICAL):
                assert result.metadata.get("quarantined") is True

    def test_calculate_entropy(self, validator):
        """Test entropy calculation."""
        # Low entropy (repetitive)
        low_entropy = validator._calculate_entropy("aaaaaaaaaaa")
        assert low_entropy == 0.0

        # Higher entropy (varied)
        high_entropy = validator._calculate_entropy("abcdefghij")
        assert high_entropy > 0

    def test_get_stats(self, validator):
        """Test getting statistics."""
        stats = validator.get_stats()

        assert "total_validations" in stats
        assert "threats_detected" in stats
        assert "quarantined" in stats


class TestGlobalFunctions:
    """Tests for module-level functions."""

    def test_get_content_validator(self):
        """Test getting global content validator."""
        with patch("forge.resilience.security.content_validator._content_validator", None):
            with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.content_validation.enabled = True
                mock_config.content_validation.anomaly_threshold = 0.8
                mock_config.content_validation.max_content_length = 1000000
                mock_config.content_validation.enable_ml_classification = False
                mock.return_value = mock_config

                validator = get_content_validator()

                assert isinstance(validator, ContentValidator)
                assert validator._initialized is True

    @pytest.mark.asyncio
    async def test_validate_content_function(self):
        """Test convenience validate_content function."""
        with patch("forge.resilience.security.content_validator._content_validator", None):
            with patch("forge.resilience.security.content_validator.get_resilience_config") as mock:
                mock_config = MagicMock()
                mock_config.content_validation.enabled = True
                mock_config.content_validation.anomaly_threshold = 0.8
                mock_config.content_validation.max_content_length = 1000000
                mock_config.content_validation.enable_ml_classification = False
                mock_config.content_validation.quarantine_on_threat = True
                mock_config.content_validation.log_threats = True
                mock.return_value = mock_config

                result = await validate_content("Clean content here")

                assert isinstance(result, ValidationResult)
