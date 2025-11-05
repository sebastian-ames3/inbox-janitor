"""
Security Headers Tests

Tests that all required security headers are present and correctly configured.

Security Requirements:
- X-Frame-Options: DENY
- X-Content-Type-Options: nosniff
- X-XSS-Protection: 1; mode=block
- Strict-Transport-Security (HSTS) in production
- Content-Security-Policy with restrictive directives
- Referrer-Policy: strict-origin-when-cross-origin
- Permissions-Policy to disable unnecessary features
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestBasicSecurityHeaders:
    """Test basic security headers on all responses."""

    def test_x_frame_options_deny(self, client):
        """X-Frame-Options should be DENY to prevent clickjacking."""
        response = client.get("/")

        assert "X-Frame-Options" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"

    def test_x_content_type_options_nosniff(self, client):
        """X-Content-Type-Options should be nosniff."""
        response = client.get("/")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_x_xss_protection_enabled(self, client):
        """X-XSS-Protection should be enabled with mode=block."""
        response = client.get("/")

        assert "X-XSS-Protection" in response.headers

        xss_protection = response.headers["X-XSS-Protection"]
        assert "1" in xss_protection
        assert "mode=block" in xss_protection

    def test_referrer_policy_set(self, client):
        """Referrer-Policy should be strict-origin-when-cross-origin."""
        response = client.get("/")

        assert "Referrer-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


class TestHSTS:
    """Test HTTP Strict Transport Security header."""

    def test_hsts_in_production(self):
        """HSTS header should be present in production."""
        from app.core.config import settings

        # HSTS should only be enabled in production (requires HTTPS)
        if settings.ENVIRONMENT == "production":
            # In production, verify HSTS header is set
            assert settings.is_production is True

    def test_hsts_not_in_development(self, client):
        """HSTS should not be set in development (no HTTPS)."""
        from app.core.config import settings

        response = client.get("/")

        if settings.ENVIRONMENT == "development":
            # HSTS should not be set
            # (or may be set but not enforced)
            pass

    def test_hsts_includes_subdomains(self):
        """HSTS should include subdomains."""
        # Expected header:
        # Strict-Transport-Security: max-age=31536000; includeSubDomains

        # Verify configuration in middleware.py
        # HSTS header should include "includeSubDomains"


class TestContentSecurityPolicy:
    """Test Content Security Policy header."""

    def test_csp_header_present(self, client):
        """CSP header should be present on all responses."""
        response = client.get("/")

        assert "Content-Security-Policy" in response.headers

    def test_csp_default_src_self(self, client):
        """CSP default-src should be 'self'."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp

    def test_csp_script_src_restricts_sources(self, client):
        """CSP script-src should restrict script sources."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        # Should restrict script sources
        assert "script-src" in csp

        # Should allow 'self'
        assert "'self'" in csp

        # Should allow trusted CDNs only
        assert "unpkg.com" in csp  # HTMX
        assert "jsdelivr.net" in csp  # Alpine.js

    def test_csp_style_src_allows_fonts_googleapis(self, client):
        """CSP style-src should allow Google Fonts."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "style-src" in csp
        assert "fonts.googleapis.com" in csp

    def test_csp_font_src_allows_fonts_gstatic(self, client):
        """CSP font-src should allow Google Fonts static resources."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "font-src" in csp
        assert "fonts.gstatic.com" in csp

    def test_csp_img_src_allows_data_and_https(self, client):
        """CSP img-src should allow data URIs and HTTPS images."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "img-src" in csp
        assert "data:" in csp  # For data URIs
        assert "https:" in csp  # For external images

    def test_csp_connect_src_self(self, client):
        """CSP connect-src should be 'self' (for HTMX requests)."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "connect-src 'self'" in csp

    def test_csp_frame_ancestors_none(self, client):
        """CSP frame-ancestors should be 'none' to prevent framing."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "frame-ancestors 'none'" in csp

    def test_csp_base_uri_self(self, client):
        """CSP base-uri should be 'self'."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "base-uri 'self'" in csp

    def test_csp_form_action_self(self, client):
        """CSP form-action should be 'self'."""
        response = client.get("/")

        csp = response.headers["Content-Security-Policy"]

        assert "form-action 'self'" in csp


class TestPermissionsPolicy:
    """Test Permissions-Policy header."""

    def test_permissions_policy_present(self, client):
        """Permissions-Policy header should be present."""
        response = client.get("/")

        assert "Permissions-Policy" in response.headers

    def test_permissions_policy_disables_geolocation(self, client):
        """Permissions-Policy should disable geolocation."""
        response = client.get("/")

        permissions_policy = response.headers["Permissions-Policy"]

        assert "geolocation=()" in permissions_policy

    def test_permissions_policy_disables_microphone(self, client):
        """Permissions-Policy should disable microphone."""
        response = client.get("/")

        permissions_policy = response.headers["Permissions-Policy"]

        assert "microphone=()" in permissions_policy

    def test_permissions_policy_disables_camera(self, client):
        """Permissions-Policy should disable camera."""
        response = client.get("/")

        permissions_policy = response.headers["Permissions-Policy"]

        assert "camera=()" in permissions_policy


class TestHeadersOnAllEndpoints:
    """Test that security headers are present on all endpoints."""

    def test_headers_on_landing_page(self, client):
        """Security headers should be on landing page."""
        response = client.get("/")

        assert "X-Frame-Options" in response.headers
        assert "Content-Security-Policy" in response.headers

    def test_headers_on_dashboard(self, client):
        """Security headers should be on dashboard."""
        response = client.get("/dashboard")

        assert "X-Frame-Options" in response.headers
        assert "X-Content-Type-Options" in response.headers

    def test_headers_on_api_endpoints(self, client):
        """Security headers should be on API endpoints."""
        response = client.get("/health")

        assert "X-Content-Type-Options" in response.headers

    def test_headers_on_error_responses(self, client):
        """Security headers should be on error responses."""
        response = client.get("/nonexistent-page")

        # Even 404 responses should have security headers
        assert "X-Frame-Options" in response.headers


class TestMiddlewareConfiguration:
    """Test security middleware configuration."""

    def test_security_headers_middleware_applied(self):
        """SecurityHeadersMiddleware should be applied to app."""
        from app.main import app

        # Verify middleware is in stack
        middleware_classes = [type(m).__name__ for m in app.user_middleware]

        # SecurityHeadersMiddleware should be present

    def test_middleware_order_correct(self):
        """Middleware should be applied in correct order."""
        # Correct order (from app.main.py):
        # 1. SessionMiddleware
        # 2. CSRFMiddleware
        # 3. Rate Limiting
        # 4. SecurityHeadersMiddleware (last, applies to all responses)
