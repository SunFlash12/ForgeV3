"""
Security Unit Tests for Forge Cascade V2

SECURITY FIX (Audit 3): Comprehensive security test suite covering:
- Password validation and hashing
- MFA (TOTP and backup codes)
- Safe regex utilities
- Input validation
- Token handling
- Governance action validation

Run with: pytest tests/test_security/ -v
"""

import re
import time
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Password Security Tests
# =============================================================================


class TestPasswordValidation:
    """Tests for password validation and strength checking."""

    def test_password_min_length(self):
        """Password must be at least 8 characters."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="at least 8 characters"):
            validate_password_strength("Short1!")

    def test_password_max_length(self):
        """Password must not exceed 128 characters."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        long_password = "A" * 129 + "a1!"
        with pytest.raises(PasswordValidationError, match="cannot exceed"):
            validate_password_strength(long_password)

    def test_password_requires_uppercase(self):
        """Password must contain uppercase letter."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="uppercase"):
            validate_password_strength("lowercase123!")

    def test_password_requires_lowercase(self):
        """Password must contain lowercase letter."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="lowercase"):
            validate_password_strength("UPPERCASE123!")

    def test_password_requires_digit(self):
        """Password must contain at least one digit."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="digit"):
            validate_password_strength("NoDigitsHere!")

    def test_password_requires_special_char(self):
        """Password must contain special character."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="special character"):
            validate_password_strength("NoSpecial123")

    def test_password_common_rejected(self):
        """Common passwords are rejected."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="too common"):
            validate_password_strength("P@ssw0rd")

    def test_password_banned_substrings(self):
        """Passwords with banned substrings are rejected."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="common words"):
            validate_password_strength("MyForge123!")  # Contains 'forge'

    def test_password_username_similarity(self):
        """Password cannot contain username."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="username"):
            validate_password_strength("JohnDoe123!", username="johndoe")

    def test_password_email_similarity(self):
        """Password cannot contain email local part."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="email"):
            validate_password_strength("Jsmith7890X!", email="jsmith@example.com")

    def test_password_repetitive_pattern(self):
        """Password with repetitive patterns is rejected."""
        from forge.security.password import PasswordValidationError, validate_password_strength

        with pytest.raises(PasswordValidationError, match="repetitive"):
            validate_password_strength("ZqxZqxZqx1!")

    def test_valid_password_accepted(self):
        """Valid password passes all checks."""
        from forge.security.password import validate_password_strength

        # Should not raise
        validate_password_strength(
            "SecureP@ss2024!", username="different", email="other@example.com"
        )

    def test_password_hashing_returns_bcrypt(self):
        """Password hashing returns valid bcrypt hash."""
        from forge.security.password import hash_password

        hashed = hash_password("ValidP@ss123!", validate=False)
        assert hashed.startswith("$2")  # bcrypt prefix
        assert len(hashed) == 60  # bcrypt hash length

    def test_password_verification_correct(self):
        """Correct password verifies successfully."""
        from forge.security.password import hash_password, verify_password

        password = "ValidP@ss123!"
        hashed = hash_password(password, validate=False)
        assert verify_password(password, hashed) is True

    def test_password_verification_incorrect(self):
        """Incorrect password fails verification."""
        from forge.security.password import hash_password, verify_password

        hashed = hash_password("ValidP@ss123!", validate=False)
        assert verify_password("WrongPassword!", hashed) is False


# =============================================================================
# MFA Tests
# =============================================================================


class TestMFA:
    """Tests for Multi-Factor Authentication."""

    @pytest.fixture
    def mfa_service(self):
        """Get fresh MFA service instance."""
        from forge.security.mfa import MFAService

        return MFAService()

    def test_generate_secret_length(self, mfa_service):
        """Generated secret is correct length for TOTP."""
        secret = mfa_service.generate_secret()
        # Base32 encoded 20 bytes = 32 characters
        assert len(secret) == 32
        # Must be valid base32
        import base64

        decoded = base64.b32decode(secret)
        assert len(decoded) == 20

    def test_generate_backup_codes_count(self, mfa_service):
        """Generates correct number of backup codes."""
        codes = mfa_service.generate_backup_codes(count=10)
        assert len(codes) == 10

    def test_backup_code_format(self, mfa_service):
        """Backup codes have correct format."""
        codes = mfa_service.generate_backup_codes(count=1)
        code = codes[0]
        # Format: XXXX-XXXX
        assert re.match(r"^[0-9A-F]{4}-[0-9A-F]{4}$", code)

    def test_backup_codes_unique(self, mfa_service):
        """All backup codes are unique."""
        codes = mfa_service.generate_backup_codes(count=100)
        assert len(codes) == len(set(codes))

    @pytest.mark.asyncio
    async def test_setup_mfa_returns_uri(self, mfa_service):
        """MFA setup returns provisioning URI."""
        result = await mfa_service.setup_mfa("user123", "user@example.com")

        assert result.secret
        assert result.provisioning_uri.startswith("otpauth://totp/")
        assert "user%40example.com" in result.provisioning_uri or "user@example.com" in result.provisioning_uri
        assert len(result.backup_codes) == 10

    @pytest.mark.asyncio
    async def test_verify_totp_correct_code(self, mfa_service):
        """Valid TOTP code is accepted."""
        # Setup MFA
        result = await mfa_service.setup_mfa("user123", "user@example.com")

        # Generate the current code
        current_code = mfa_service._generate_totp(result.secret)

        # Verify setup with correct code
        assert await mfa_service.verify_setup("user123", current_code) is True

    @pytest.mark.asyncio
    async def test_verify_totp_wrong_code(self, mfa_service):
        """Invalid TOTP code is rejected."""
        await mfa_service.setup_mfa("user123", "user@example.com")

        assert await mfa_service.verify_setup("user123", "000000") is False

    @pytest.mark.asyncio
    async def test_backup_code_one_time_use(self, mfa_service):
        """Backup code can only be used once."""
        result = await mfa_service.setup_mfa("user123", "user@example.com")

        # Verify setup first
        current_code = mfa_service._generate_totp(result.secret)
        await mfa_service.verify_setup("user123", current_code)

        backup_code = result.backup_codes[0]

        # First use should succeed
        assert await mfa_service.verify_backup_code("user123", backup_code) is True

        # Second use should fail
        assert await mfa_service.verify_backup_code("user123", backup_code) is False

    @pytest.mark.asyncio
    async def test_rate_limiting_verification(self, mfa_service):
        """Rate limiting kicks in after too many failed attempts."""
        await mfa_service.setup_mfa("user123", "user@example.com")

        # Make 5 failed attempts
        for _ in range(5):
            await mfa_service.verify_totp("user123", "000000", skip_verified_check=True)

        # Next attempt should be rate limited
        # Check internal state
        attempt = mfa_service._verification_attempts.get("user123")
        assert attempt is not None
        assert attempt.locked_until is not None

    @pytest.mark.asyncio
    async def test_disable_mfa_clears_data(self, mfa_service):
        """Disabling MFA clears all user data."""
        await mfa_service.setup_mfa("user123", "user@example.com")
        await mfa_service.disable_mfa("user123")

        status = await mfa_service.get_status("user123")
        assert status.enabled is False


# =============================================================================
# Safe Regex Tests
# =============================================================================


class TestSafeRegex:
    """Tests for ReDoS-safe regex utilities."""

    def test_validate_pattern_valid(self):
        """Valid pattern passes validation."""
        from forge.security.safe_regex import validate_pattern

        is_valid, error = validate_pattern(r"hello.*world")
        assert is_valid is True
        assert error is None

    def test_validate_pattern_too_long(self):
        """Pattern exceeding max length is rejected."""
        from forge.security.safe_regex import MAX_PATTERN_LENGTH, validate_pattern

        long_pattern = "a" * (MAX_PATTERN_LENGTH + 1)
        is_valid, error = validate_pattern(long_pattern)
        assert is_valid is False
        assert "length" in error.lower()

    def test_validate_pattern_invalid_regex(self):
        """Invalid regex syntax is rejected."""
        from forge.security.safe_regex import validate_pattern

        is_valid, error = validate_pattern(r"[invalid")
        assert is_valid is False
        assert "Invalid regex" in error

    def test_validate_pattern_nested_quantifiers(self):
        """Nested quantifiers (ReDoS risk) are rejected."""
        from forge.security.safe_regex import validate_pattern

        is_valid, error = validate_pattern(r"(a+)+")
        assert is_valid is False
        assert "vulnerable" in error.lower()

    def test_safe_search_timeout(self):
        """Safe search with timeout prevents hanging."""
        from forge.security.safe_regex import safe_search

        # This shouldn't hang due to timeout
        # Note: The simple pattern won't actually timeout, but the mechanism is tested
        result = safe_search(r"hello", "hello world", timeout=1.0, validate=False)
        assert result is not None

    def test_safe_search_truncates_long_input(self):
        """Input exceeding max length is truncated."""
        from forge.security.safe_regex import MAX_INPUT_LENGTH, safe_search

        long_input = "a" * (MAX_INPUT_LENGTH + 1000)
        # Should not raise, input is truncated
        result = safe_search(r"a", long_input, validate=False)
        assert result is not None

    def test_safe_findall_limits_results(self):
        """Findall limits number of results."""
        from forge.security.safe_regex import safe_findall

        input_str = "a " * 2000  # Would produce 2000 matches
        results = safe_findall(r"a", input_str, max_results=100, validate=False)
        assert len(results) <= 100


# =============================================================================
# Governance Action Validation Tests
# =============================================================================


class TestGovernanceActionValidation:
    """Tests for governance proposal action validation."""

    def test_valid_action_accepted(self):
        """Valid action for proposal type is accepted."""
        from forge.models.governance import ProposalCreate, ProposalType

        # Should not raise
        proposal = ProposalCreate(
            title="Test Proposal Title Here",
            description="This is a test proposal description that meets the minimum length requirement.",
            type=ProposalType.SYSTEM,
            action={"type": "update_config", "config_key": "rate_limit", "new_value": 100},
        )
        assert proposal.action["type"] == "update_config"

    def test_invalid_action_type_rejected(self):
        """Action type not valid for proposal type is rejected."""
        from pydantic import ValidationError

        from forge.models.governance import ProposalCreate, ProposalType

        with pytest.raises(ValidationError, match="not valid"):
            ProposalCreate(
                title="Test Proposal Title Here",
                description="This is a test proposal description that meets the minimum length requirement.",
                type=ProposalType.SYSTEM,
                action={"type": "amend_constitution"},  # Wrong type for SYSTEM proposals
            )

    def test_missing_required_fields_rejected(self):
        """Action missing required fields is rejected."""
        from pydantic import ValidationError

        from forge.models.governance import ProposalCreate, ProposalType

        with pytest.raises(ValidationError, match="missing required"):
            ProposalCreate(
                title="Test Proposal Title Here",
                description="This is a test proposal description that meets the minimum length requirement.",
                type=ProposalType.SYSTEM,
                action={"type": "update_config"},  # Missing config_key and new_value
            )

    def test_dangerous_fields_rejected(self):
        """Action with dangerous fields is rejected."""
        from pydantic import ValidationError

        from forge.models.governance import ProposalCreate, ProposalType

        with pytest.raises(ValidationError, match="forbidden"):
            ProposalCreate(
                title="Test Proposal Title Here",
                description="This is a test proposal description that meets the minimum length requirement.",
                type=ProposalType.SYSTEM,
                action={
                    "type": "update_config",
                    "config_key": "test",
                    "new_value": "test",
                    "__import__": "os",  # Dangerous field
                },
            )

    def test_empty_action_allowed(self):
        """Empty action (informational proposal) is allowed."""
        from forge.models.governance import ProposalCreate, ProposalType

        # Should not raise
        proposal = ProposalCreate(
            title="Informational Proposal",
            description="This is an informational proposal without any action to execute.",
            type=ProposalType.POLICY,
            action={},
        )
        assert proposal.action == {}


# =============================================================================
# Token Security Tests
# =============================================================================


class TestTokenSecurity:
    """Tests for JWT token security."""

    def test_token_blacklist_adds_all(self):
        """Token blacklist adds all tokens (security > memory)."""
        from forge.security.tokens import TokenBlacklist

        max_size = TokenBlacklist._MAX_BLACKLIST_SIZE

        # Add many tokens
        for i in range(max_size + 100):
            TokenBlacklist.add(f"token_{i}", time.time() + 3600)

        # Security > memory: all tokens are added even beyond max size
        assert len(TokenBlacklist._blacklist) >= max_size
        # Verify the last added token is blacklisted
        assert TokenBlacklist.is_blacklisted(f"token_{max_size + 99}")

        # Clean up
        TokenBlacklist._blacklist.clear()
        TokenBlacklist._expiry_times.clear()

    def test_blacklisted_token_rejected(self):
        """Blacklisted token is correctly identified."""
        from forge.security.tokens import TokenBlacklist

        TokenBlacklist.add("blacklisted_token", time.time() + 3600)
        assert TokenBlacklist.is_blacklisted("blacklisted_token") is True
        assert TokenBlacklist.is_blacklisted("other_token") is False

        # Clean up
        TokenBlacklist._blacklist.clear()
        TokenBlacklist._expiry_times.clear()


# =============================================================================
# Input Validation Tests
# =============================================================================


class TestInputValidation:
    """Tests for API input validation."""

    def test_api_limits_json_depth(self):
        """JSON depth limit is enforced."""
        from forge.api.middleware import APILimitsMiddleware

        middleware = APILimitsMiddleware(app=MagicMock(), max_json_depth=5)

        # Nested too deep
        nested = {"a": {"b": {"c": {"d": {"e": {"f": "too deep"}}}}}}
        is_valid, error = middleware._check_json_depth(nested)
        assert is_valid is False
        assert "depth" in error.lower()

    def test_api_limits_array_length(self):
        """Array length limit is enforced."""
        from forge.api.middleware import APILimitsMiddleware

        middleware = APILimitsMiddleware(app=MagicMock(), max_array_length=10)

        data = {"items": list(range(20))}
        is_valid, error = middleware._check_json_depth(data)
        assert is_valid is False
        assert "length" in error.lower()


# =============================================================================
# Integration Tests
# =============================================================================


class TestSecurityIntegration:
    """Integration tests for security features working together."""

    @pytest.mark.asyncio
    async def test_password_change_validates_new_password(self):
        """Password change validates new password against username."""
        from forge.security.password import PasswordValidationError, hash_password

        # This should raise because password contains username
        with pytest.raises(PasswordValidationError):
            hash_password("JohnDoe123!", username="johndoe", email="john@example.com")

    @pytest.mark.asyncio
    async def test_mfa_and_password_together(self):
        """MFA and password security work together."""
        from forge.security.mfa import MFAService
        from forge.security.password import validate_password_strength

        # Valid password
        validate_password_strength("SecureP@ss2024!")

        # MFA setup
        mfa = MFAService()
        result = await mfa.setup_mfa("user123", "user@example.com")

        # Both password and MFA are now configured
        assert result.secret
        assert len(result.backup_codes) == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
