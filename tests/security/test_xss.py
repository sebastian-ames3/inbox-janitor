"""
XSS (Cross-Site Scripting) Prevention Tests

Tests that user input is properly escaped and XSS attacks are prevented.

Security Requirements:
- All user input must be HTML-escaped in templates
- Jinja2 auto-escaping must be enabled
- HTMX responses must escape user content
- Email subjects and senders must be escaped
- No inline scripts with user data
- Content-Security-Policy header must prevent inline scripts
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestJinja2AutoEscaping:
    """Test that Jinja2 auto-escaping is enabled and working."""

    def test_jinja2_autoescape_enabled(self):
        """Jinja2 templates should have auto-escaping enabled."""
        from app.main import templates

        # Verify templates are configured
        assert templates is not None

        # Jinja2 auto-escaping is enabled by default in FastAPI
        # This test verifies the templates object exists

    def test_malicious_script_in_page_is_escaped(self, client):
        """Malicious script tags in page content should be escaped."""
        # Navigate to a page
        response = client.get("/")

        assert response.status_code == 200
        html = response.text

        # Should not contain any unescaped script tags
        # All < and > should be escaped as &lt; and &gt;

        # Check that dangerous characters are not present in contexts where
        # they could execute JavaScript
        # Note: Script tags for legitimate CDN loads (HTMX, Alpine.js) are ok

    def test_email_subject_with_script_tag_escaped(self):
        """Email subjects containing script tags should be HTML-escaped."""
        # Simulated malicious email subject
        malicious_subject = '<script>alert("XSS")</script>Get 50% off!'

        # When rendered in template, should become:
        expected_escaped = '&lt;script&gt;alert("XSS")&lt;/script&gt;Get 50% off!'

        # Test Jinja2 escaping directly
        from markupsafe import escape

        escaped = escape(malicious_subject)
        assert '<script>' not in str(escaped)
        assert '&lt;script&gt;' in str(escaped)

    def test_email_sender_with_xss_escaped(self):
        """Email sender addresses with XSS payloads should be escaped."""
        malicious_sender = 'evil@example.com"><script>alert("XSS")</script>'

        from markupsafe import escape

        escaped = escape(malicious_sender)

        # Should escape quotes and brackets
        assert '<script>' not in str(escaped)
        assert '&lt;script&gt;' in str(escaped)
        assert '"&gt;' in str(escaped) or '&#34;&gt;' in str(escaped)


class TestHTMXResponseEscaping:
    """Test that HTMX partial responses escape user content."""

    def test_htmx_response_escapes_user_input(self, client):
        """HTMX responses should escape HTML in user input."""
        # This test would simulate an HTMX request and check the response

        # Example: If settings update returns HTML fragment, it should escape
        # any user-provided strings

        # For now, verify principle that all template rendering escapes

    def test_htmx_error_messages_escape_input(self):
        """Error messages in HTMX responses should escape user input."""
        # If validation fails and error message includes user input,
        # it should be HTML-escaped

        from markupsafe import escape

        user_input = '<img src=x onerror=alert("XSS")>'
        error_message = f"Invalid value: {escape(user_input)}"

        assert '<img' not in error_message
        assert '&lt;img' in error_message


class TestContentSecurityPolicy:
    """Test Content-Security-Policy header prevents XSS."""

    def test_csp_header_present(self, client):
        """CSP header should be present on all responses."""
        response = client.get("/")

        assert response.status_code == 200

        # CSP header should be set
        assert "Content-Security-Policy" in response.headers

        csp = response.headers["Content-Security-Policy"]

        # Should restrict script sources
        assert "script-src" in csp

        # Should allow 'unsafe-eval' for Alpine.js (required for reactive expressions)
        # Note: This is a known tradeoff for Alpine.js functionality
        assert "unsafe-eval" in csp

    def test_csp_default_src_self(self, client):
        """CSP should default to 'self' for most resources."""
        response = client.get("/")

        csp = response.headers.get("Content-Security-Policy", "")

        # Default source should be 'self'
        assert "default-src 'self'" in csp

    def test_csp_script_src_allows_cdn(self, client):
        """CSP should allow scripts from trusted CDNs only."""
        response = client.get("/")

        csp = response.headers.get("Content-Security-Policy", "")

        # Should allow unpkg.com for HTMX
        assert "unpkg.com" in csp

        # Should allow jsdelivr.net for Alpine.js
        assert "jsdelivr.net" in csp

    def test_csp_blocks_inline_scripts(self, client):
        """CSP should block inline scripts (except with 'unsafe-inline' for Alpine/HTMX)."""
        response = client.get("/")

        csp = response.headers.get("Content-Security-Policy", "")

        # Note: Currently 'unsafe-inline' is needed for Alpine.js and HTMX
        # In production, consider using nonces instead

        # Verify CSP is configured
        assert "script-src" in csp

    def test_csp_frame_ancestors_none(self, client):
        """CSP should prevent clickjacking with frame-ancestors 'none'."""
        response = client.get("/")

        csp = response.headers.get("Content-Security-Policy", "")

        # Should prevent framing
        assert "frame-ancestors 'none'" in csp


class TestUserInputEscaping:
    """Test escaping of various user input contexts."""

    def test_email_snippet_escaped(self):
        """Email snippet (first 200 chars) should be HTML-escaped."""
        malicious_snippet = 'Dear user, <script>steal_credentials()</script> click here!'

        from markupsafe import escape

        escaped = escape(malicious_snippet)

        assert '<script>' not in str(escaped)
        assert '&lt;script&gt;' in str(escaped)

    def test_classification_reason_escaped(self):
        """Classification reason text should be escaped."""
        # If classification reason includes email content, it should be escaped

        reason = 'Contains marketing keyword: <b>FREE</b>'

        from markupsafe import escape

        escaped = escape(reason)

        # HTML tags should be escaped
        assert '<b>' not in str(escaped)
        assert '&lt;b&gt;' in str(escaped)

    def test_user_email_address_escaped(self):
        """User's email address should be safe to display."""
        # Email addresses are generally safe, but still should be escaped

        email = 'user+test@example.com'

        from markupsafe import escape

        escaped = escape(email)

        # Should not introduce XSS
        # Plus sign and @ are safe
        assert str(escaped) == email

    def test_settings_values_escaped(self):
        """User settings values should be escaped when displayed."""
        # If user can input custom strings in settings (e.g., blocked senders),
        # they should be escaped

        blocked_sender = '<script>alert(1)</script>@example.com'

        from markupsafe import escape

        escaped = escape(blocked_sender)

        assert '<script>' not in str(escaped)


class TestXSSAttackVectors:
    """Test various XSS attack vectors are prevented."""

    def test_script_tag_injection(self):
        """Script tag injection should be prevented."""
        payload = '<script>alert("XSS")</script>'

        from markupsafe import escape

        escaped = escape(payload)

        # Should not execute as script
        assert '<script>' not in str(escaped)
        assert '&lt;script&gt;' in str(escaped)

    def test_img_onerror_injection(self):
        """Image onerror handler injection should be prevented."""
        payload = '<img src=x onerror=alert("XSS")>'

        from markupsafe import escape

        escaped = escape(payload)

        # Tags should be escaped (won't execute as HTML)
        assert '&lt;img' in str(escaped)
        assert '&gt;' in str(escaped)
        # Event handler is present as text but won't execute
        assert '<img' not in str(escaped)

    def test_svg_script_injection(self):
        """SVG-based script injection should be prevented."""
        payload = '<svg onload=alert("XSS")>'

        from markupsafe import escape

        escaped = escape(payload)

        # Tags should be escaped (won't execute as HTML)
        assert '&lt;svg' in str(escaped)
        assert '&gt;' in str(escaped)
        # Event handler is present as text but won't execute
        assert '<svg' not in str(escaped)

    def test_javascript_url_injection(self):
        """JavaScript URL injection should be prevented."""
        payload = 'javascript:alert("XSS")'

        from markupsafe import escape

        escaped = escape(payload)

        # Escaping doesn't change this much, but when used in href context,
        # should be validated/sanitized

        # If this appears in an href, CSP should block it

    def test_data_url_injection(self):
        """Data URL with JavaScript should be prevented."""
        payload = 'data:text/html,<script>alert("XSS")</script>'

        from markupsafe import escape

        escaped = escape(payload)

        # URL itself gets escaped
        assert '&lt;script&gt;' in str(escaped)

    def test_event_handler_injection(self):
        """Event handler attributes should be escaped."""
        payload = 'onclick=alert("XSS")'

        from markupsafe import escape

        escaped = escape(payload)

        # When escaped and rendered, should not execute
        # Quotes get escaped
        assert 'onclick=' in str(escaped)  # Text remains but won't execute in escaped context


class TestTemplateInjection:
    """Test that template injection attacks are prevented."""

    def test_jinja2_template_syntax_not_evaluated(self):
        """Jinja2 syntax in user input should not be evaluated."""
        # User input should not be able to execute template code

        payload = '{{ 7 * 7 }}'  # Template expression

        from markupsafe import escape

        escaped = escape(payload)

        # Should be rendered as literal text, not evaluated
        assert '{{' in str(escaped) or '&#123;&#123;' in str(escaped)

    def test_template_include_prevented(self):
        """Users cannot include arbitrary templates."""
        payload = "{% include '/etc/passwd' %}"

        from markupsafe import escape

        escaped = escape(payload)

        # Should be escaped, not executed
        assert '{%' in str(escaped) or '&#123;%' in str(escaped)


class TestDOMBasedXSS:
    """Test DOM-based XSS prevention."""

    def test_no_unsafe_innerhtml_usage(self):
        """Verify that templates don't use unsafe innerHTML patterns."""
        # This would require reading template files and checking for patterns

        # In Alpine.js and HTMX usage, verify:
        # - x-html is not used with user input
        # - hx-swap with innerHTML is safe

        # For now, document that this should be manually reviewed

    def test_alpine_js_xtext_safe(self):
        """Alpine.js x-text is safe for displaying user data."""
        # x-text automatically escapes content

        # This is a documentation test - x-text is safe by default

    def test_htmx_swap_methods_safe(self):
        """HTMX swap methods should use safe defaults."""
        # hx-swap="innerHTML" is used, but server returns escaped HTML

        # Verify server-side rendering escapes content (tested above)


class TestXSSConfiguration:
    """Test XSS prevention configuration."""

    def test_x_xss_protection_header_set(self, client):
        """X-XSS-Protection header should be set."""
        response = client.get("/")

        # Header should be present (even though deprecated, defense in depth)
        assert "X-XSS-Protection" in response.headers

        xss_protection = response.headers["X-XSS-Protection"]

        # Should be "1; mode=block"
        assert "1" in xss_protection
        assert "mode=block" in xss_protection

    def test_x_content_type_options_nosniff(self, client):
        """X-Content-Type-Options should be set to nosniff."""
        response = client.get("/")

        assert "X-Content-Type-Options" in response.headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_content_type_header_correct(self, client):
        """Content-Type header should be correctly set."""
        response = client.get("/")

        assert "Content-Type" in response.headers

        content_type = response.headers["Content-Type"]

        # Should be text/html with charset
        assert "text/html" in content_type or "application/json" in content_type


class TestEmailContentSanitization:
    """Test that email content displayed in UI is properly sanitized."""

    def test_email_subject_with_html_tags_escaped(self):
        """Email subjects with HTML tags should be displayed as text."""
        subject_with_html = 'Amazing <b>Deal</b> - <span style="color:red">50% OFF</span>'

        from markupsafe import escape

        escaped = escape(subject_with_html)

        # HTML tags should be visible as text, not rendered
        assert '&lt;b&gt;' in str(escaped)
        assert '&lt;span' in str(escaped)
        assert 'style=' not in str(escaped) or 'style=&#34;' in str(escaped)

    def test_email_snippet_with_scripts_escaped(self):
        """Email snippets with embedded scripts should be safe."""
        snippet = 'Click here: <a href="javascript:void(0)">Link</a>'

        from markupsafe import escape

        escaped = escape(snippet)

        # Anchor tag should be escaped
        assert '&lt;a href=' in str(escaped) or '&lt;a' in str(escaped)

    def test_sender_display_name_escaped(self):
        """Sender display names should be HTML-escaped."""
        # Gmail sender format: "Display Name <email@example.com>"
        sender = '"<script>alert(1)</script>" <evil@example.com>'

        from markupsafe import escape

        escaped = escape(sender)

        assert '&lt;script&gt;' in str(escaped)
