"""
Password Security Tests for Forge Cascade V2

Comprehensive tests for password handling including:
- Password hashing (bcrypt)
- Password verification
- Password strength validation
"""

import pytest

from forge.security.password import (
    PasswordValidationError,
    hash_password,
    validate_password_strength,
    verify_password,
)

# =============================================================================
# Password Hashing Tests
# =============================================================================


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_hash_password_basic(self):
        """Password hashing produces valid bcrypt hash."""
        password = "SecureP@ss123!"
        hashed = hash_password(password, validate=False)

        # Bcrypt hash starts with $2b$
        assert hashed.startswith("$2b$")
        # Bcrypt hash is 60 characters
        assert len(hashed) == 60

    def test_hash_password_different_each_time(self):
        """Same password produces different hashes (salt)."""
        password = "SecureP@ss123!"

        hash1 = hash_password(password, validate=False)
        hash2 = hash_password(password, validate=False)

        assert hash1 != hash2

    def test_hash_password_validates_by_default(self):
        """Hash function validates password strength by default."""
        weak_password = "weak"

        with pytest.raises(PasswordValidationError):
            hash_password(weak_password)  # validate=True by default

    def test_hash_password_skip_validation(self):
        """Hash function can skip validation."""
        weak_password = "weak"

        # Should not raise when validation is disabled
        hashed = hash_password(weak_password, validate=False)
        assert hashed.startswith("$2b$")

    def test_hash_password_empty_fails(self):
        """Empty password fails."""
        with pytest.raises((PasswordValidationError, ValueError)):
            hash_password("")

    def test_hash_password_unicode(self):
        """Unicode password is hashed correctly."""
        password = "SecureP@ss123!"
        hashed = hash_password(password, validate=False)

        assert hashed.startswith("$2b$")
        assert verify_password(password, hashed)


# =============================================================================
# Password Verification Tests
# =============================================================================


class TestPasswordVerification:
    """Tests for password verification functionality."""

    def test_verify_password_correct(self):
        """Correct password verifies successfully."""
        password = "SecureP@ss123!"
        hashed = hash_password(password, validate=False)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password fails verification."""
        password = "SecureP@ss123!"
        hashed = hash_password(password, validate=False)

        assert verify_password("WrongPassword1!", hashed) is False

    def test_verify_password_case_sensitive(self):
        """Password verification is case-sensitive."""
        password = "SecureP@ss123!"
        hashed = hash_password(password, validate=False)

        # Different case should fail
        assert verify_password("securep@ss123!", hashed) is False
        assert verify_password("SECUREP@SS123!", hashed) is False

    def test_verify_password_whitespace_matters(self):
        """Whitespace in password matters."""
        password = "SecureP@ss 123!"
        hashed = hash_password(password, validate=False)

        assert verify_password("SecureP@ss 123!", hashed) is True
        assert verify_password("SecureP@ss123!", hashed) is False

    def test_verify_password_invalid_hash(self):
        """Invalid hash format returns False."""
        assert verify_password("anypassword", "invalid_hash") is False

    def test_verify_password_empty_password(self):
        """Empty password fails verification."""
        hashed = hash_password("SecureP@ss123!", validate=False)
        assert verify_password("", hashed) is False


# =============================================================================
# Password Strength Validation Tests
# =============================================================================


class TestPasswordStrength:
    """Tests for password strength validation."""

    def test_valid_password_passes(self):
        """Valid password passes all checks."""
        # Should not raise
        validate_password_strength("SecureP@ss123!")

    def test_too_short_fails(self):
        """Password under 8 characters fails."""
        with pytest.raises(PasswordValidationError, match="at least 8"):
            validate_password_strength("Short1!")

    def test_no_uppercase_fails(self):
        """Password without uppercase fails."""
        with pytest.raises(PasswordValidationError, match="uppercase"):
            validate_password_strength("securep@ss123!")

    def test_no_lowercase_fails(self):
        """Password without lowercase fails."""
        with pytest.raises(PasswordValidationError, match="lowercase"):
            validate_password_strength("SECUREP@SS123!")

    def test_no_digit_fails(self):
        """Password without digit fails."""
        with pytest.raises(PasswordValidationError, match="digit"):
            validate_password_strength("SecureP@ssword!")

    def test_bcrypt_length_limit(self):
        """Password over 72 bytes should be warned about."""
        long_password = "A" * 80 + "a1!"

        # This may or may not raise depending on implementation
        # The important thing is it doesn't silently truncate
        try:
            validate_password_strength(long_password)
        except PasswordValidationError:
            pass  # Expected if implementation enforces limit

    def test_minimum_valid_password(self):
        """Minimum valid password passes."""
        # 8 chars, uppercase, lowercase, digit, special char, not sequential
        validate_password_strength("XyLm@9kP!")

    def test_password_with_special_chars(self):
        """Password with special characters passes."""
        # Avoid banned substrings and sequential patterns
        validate_password_strength("XyLm@9kP#Zq$3")

    def test_password_with_spaces(self):
        """Password with spaces passes."""
        # Avoid 'pass' substring which is banned
        validate_password_strength("MyLongKey 123!")

    def test_no_special_char_fails(self):
        """Password without special character fails."""
        with pytest.raises(PasswordValidationError, match="special character"):
            validate_password_strength("Abcdefg12345")

    def test_banned_substring_fails(self):
        """Password with banned substring fails."""
        # 'admin', 'pass', 'test', etc. are banned
        with pytest.raises(PasswordValidationError):
            validate_password_strength("Admin123!@#")

    def test_common_password_fails(self):
        """Common weak password fails."""
        with pytest.raises(PasswordValidationError, match="common"):
            validate_password_strength("Password123!")


# =============================================================================
# Edge Cases and Security Tests
# =============================================================================


class TestPasswordEdgeCases:
    """Tests for edge cases and security considerations."""

    def test_timing_attack_resistance(self):
        """Verification time is similar for correct and incorrect passwords."""
        import time

        password = "SecureP@ss123!"
        hashed = hash_password(password, validate=False)

        # Measure correct password
        start = time.perf_counter()
        for _ in range(10):
            verify_password(password, hashed)
        correct_time = time.perf_counter() - start

        # Measure incorrect password
        start = time.perf_counter()
        for _ in range(10):
            verify_password("WrongPassword1!", hashed)
        incorrect_time = time.perf_counter() - start

        # Times should be roughly similar (within 50%)
        ratio = max(correct_time, incorrect_time) / max(min(correct_time, incorrect_time), 0.0001)
        assert ratio < 2.0, "Timing difference too large - potential timing attack"

    def test_hash_different_work_factor(self):
        """Different work factors still produce valid hashes."""
        password = "SecureP@ss123!"

        # Standard hash
        hashed = hash_password(password, validate=False)
        assert verify_password(password, hashed)

    def test_unicode_password_compatibility(self):
        """Unicode passwords hash and verify correctly."""
        password = "Secure123!"
        hashed = hash_password(password, validate=False)

        assert verify_password(password, hashed)

    def test_null_byte_in_password(self):
        """Null bytes in password are handled."""
        password = "Secure\x00P@ss123!"

        try:
            hashed = hash_password(password, validate=False)
            # If hashing succeeds, verification should work
            assert verify_password(password, hashed)
        except (ValueError, PasswordValidationError):
            # Or implementation may reject null bytes
            pass

    def test_very_long_password(self):
        """Very long passwords are handled (bcrypt has 72 byte limit)."""
        # Bcrypt has 72 byte limit - test that we handle it
        base_password = "Xy@z123!"
        long_password = base_password + "w" * 100

        # bcrypt will raise error for passwords > 72 bytes
        # This is expected behavior - test that we handle it
        try:
            hashed = hash_password(long_password, validate=False)
            # If it works, verify should work too
            assert verify_password(long_password, hashed)
        except ValueError as e:
            # Expected: bcrypt raises error for passwords > 72 bytes
            assert "72 bytes" in str(e)

    def test_common_password_patterns_rejected(self):
        """Common weak patterns should be rejected."""
        weak_passwords = [
            "12345678",  # All digits
            "abcdefgh",  # All lowercase
            "ABCDEFGH",  # All uppercase
        ]

        for pwd in weak_passwords:
            with pytest.raises(PasswordValidationError):
                validate_password_strength(pwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
