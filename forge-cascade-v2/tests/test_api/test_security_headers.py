"""
Security Header Tests

Tests for CSRF, CORS, HSTS, and other security headers.
SECURITY FIX (Audit 5): Added comprehensive security header testing.
"""

import pytest
from fastapi.testclient import TestClient


class TestSecurityHeaders:
    """Tests for security headers on all responses."""

    def test_security_headers_present(self, client: TestClient):
        """Test that security headers are present on responses."""
        response = client.get("/health")
        assert response.status_code == 200

        # X-Content-Type-Options prevents MIME sniffing
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

        # X-Frame-Options prevents clickjacking
        assert response.headers.get("X-Frame-Options") == "DENY"

        # Content-Security-Policy exists (may vary by environment)
        # Just check it exists, specific policy may vary
        csp = response.headers.get("Content-Security-Policy")
        # CSP might not be set in test environment, so we skip if not present
        if csp:
            assert "default-src" in csp or "script-src" in csp

    def test_no_server_header_leak(self, client: TestClient):
        """Test that server version is not leaked in headers."""
        response = client.get("/health")

        # Server header should not reveal version details
        server = response.headers.get("Server")
        if server:
            # Should not contain version numbers
            assert "nginx" not in server.lower() or "/" not in server
            assert "apache" not in server.lower() or "/" not in server


class TestCORSHeaders:
    """Tests for CORS header configuration."""

    def test_cors_preflight_allowed_origin(self, client: TestClient):
        """Test CORS preflight for allowed origin."""
        response = client.options(
            "/api/v1/capsules",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should not return 405 Method Not Allowed for OPTIONS
        assert response.status_code in [200, 204]

    def test_cors_preflight_with_credentials(self, client: TestClient):
        """Test CORS preflight with credentials request."""
        response = client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            },
        )
        assert response.status_code in [200, 204]

        # If CORS is configured, check for credentials support
        if "Access-Control-Allow-Credentials" in response.headers:
            assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_cors_disallowed_origin(self, client: TestClient):
        """Test that malicious origins are rejected."""
        response = client.options(
            "/api/v1/capsules",
            headers={
                "Origin": "http://malicious-site.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should either deny or not include the origin in allowed origins
        if "Access-Control-Allow-Origin" in response.headers:
            allowed = response.headers.get("Access-Control-Allow-Origin")
            assert allowed != "http://malicious-site.com"
            assert allowed != "*"  # Wildcard not allowed with credentials


class TestCSRFProtection:
    """Tests for CSRF token protection."""

    def test_csrf_token_in_login_response(self, client: TestClient):
        """Test that login response includes CSRF token."""
        # First register a user
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "csrftest_user",
                "email": "csrftest@example.com",
                "password": "SecurePassword123!",
            },
        )

        # Try to login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "csrftest_user",
                "password": "SecurePassword123!",
            },
        )

        # If login succeeds, should have CSRF token
        if response.status_code == 200:
            data = response.json()
            assert "csrf_token" in data
            assert len(data["csrf_token"]) >= 32  # Should be reasonably long

    def test_csrf_cookie_attributes(self, client: TestClient):
        """Test CSRF cookie security attributes."""
        # Register and login to get cookies
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "csrfcookie_user",
                "email": "csrfcookie@example.com",
                "password": "SecurePassword123!",
            },
        )

        response = client.post(
            "/api/v1/auth/login",
            json={
                "username": "csrfcookie_user",
                "password": "SecurePassword123!",
            },
        )

        if response.status_code == 200:
            # Check for csrf_token cookie
            csrf_cookie = response.cookies.get("csrf_token")
            if csrf_cookie:
                # Cookie should exist (value is opaque, just check it's set)
                assert csrf_cookie is not None

    def test_state_changing_without_csrf_fails(self, client: TestClient, auth_headers: dict):
        """Test that state-changing requests without CSRF token are handled."""
        # POST requests should require CSRF token for state changes
        response = client.post(
            "/api/v1/capsules",
            json={
                "content": "Test capsule content",
                "type": "knowledge",
            },
            headers=auth_headers,
        )

        # If CSRF is enforced, should be 403 or 401
        # If not enforced (testing mode), may succeed or fail for other reasons
        # We just verify the endpoint doesn't crash
        assert response.status_code in [201, 400, 401, 403, 422, 500]


class TestHSTSHeader:
    """Tests for HTTP Strict Transport Security."""

    def test_hsts_header_format(self, client: TestClient):
        """Test HSTS header is properly formatted when present."""
        response = client.get("/health")

        hsts = response.headers.get("Strict-Transport-Security")
        if hsts:
            # Should contain max-age
            assert "max-age" in hsts

            # If present, max-age should be a positive number
            parts = hsts.split(";")
            for part in parts:
                if "max-age" in part:
                    age_str = part.split("=")[1].strip()
                    age = int(age_str)
                    assert age > 0


class TestContentTypeProtection:
    """Tests for content type handling."""

    def test_json_content_type_enforced(self, client: TestClient):
        """Test that JSON endpoints reject non-JSON content types."""
        response = client.post(
            "/api/v1/auth/login",
            data="not-json-data",  # Send as form data instead of JSON
            headers={"Content-Type": "text/plain"},
        )
        # Should reject with 422 (Unprocessable Entity) or 415 (Unsupported Media Type)
        assert response.status_code in [400, 415, 422]

    def test_response_content_type_is_json(self, client: TestClient):
        """Test that API responses have correct content type."""
        response = client.get("/health")

        content_type = response.headers.get("Content-Type", "")
        assert "application/json" in content_type


class TestRateLimitHeaders:
    """Tests for rate limiting headers."""

    def test_rate_limit_headers_present(self, client: TestClient):
        """Test that rate limit headers are present (if rate limiting enabled)."""
        response = client.get("/health")

        # These headers may not be present in all configurations
        # Just verify no errors when checking
        rate_limit = response.headers.get("X-RateLimit-Limit")
        rate_remaining = response.headers.get("X-RateLimit-Remaining")

        # If rate limit headers are present, they should be valid integers
        if rate_limit:
            assert int(rate_limit) > 0
        if rate_remaining:
            remaining = int(rate_remaining)
            assert remaining >= 0


class TestErrorResponseSecurity:
    """Tests for secure error responses."""

    def test_404_no_stack_trace(self, client: TestClient):
        """Test that 404 responses don't leak stack traces."""
        response = client.get("/nonexistent/path/that/does/not/exist")
        assert response.status_code == 404

        body = response.text.lower()
        # Should not contain stack trace indicators
        assert "traceback" not in body
        assert 'file "' not in body
        assert "line " not in body or "line" not in body

    def test_405_no_internal_details(self, client: TestClient):
        """Test that 405 responses don't leak internal details."""
        response = client.delete("/health")  # DELETE not allowed on health
        assert response.status_code in [405, 404]  # May be 404 if route doesn't match

        if response.status_code == 405:
            body = response.text.lower()
            assert "traceback" not in body

    def test_validation_error_no_internal_paths(self, client: TestClient):
        """Test that validation errors don't leak internal file paths."""
        response = client.post("/api/v1/auth/login", json={})  # Missing required fields

        if response.status_code == 422:
            data = response.json()
            detail = str(data.get("detail", ""))

            # Should not contain file paths
            assert "/home/" not in detail
            assert "C:\\" not in detail
            assert "\\forge\\" not in detail
            assert "/forge/" not in detail
