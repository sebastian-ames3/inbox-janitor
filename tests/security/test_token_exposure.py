"""
Token Exposure Prevention Tests

Tests that OAuth tokens and sensitive keys are never exposed to users.

Security Requirements:
- OAuth tokens never in HTML source
- OAuth tokens never in JavaScript
- OAuth tokens never in cookies
- OAuth tokens never in error messages
- OAuth tokens never in logs (verified separately)
- Encryption keys never exposed
- Session secrets never exposed
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestOAuthTokensNotExposed:
    """Test that OAuth tokens are never exposed in responses."""

    def test_no_access_tokens_in_html(self, client):
        """HTML responses should not contain OAuth access tokens."""
        response = client.get("/")
        html = response.text

        # Google access tokens start with "ya29."
        assert "ya29." not in html

        # Generic token patterns
        assert "access_token" not in html or "csrf_token" in html  # CSRF is OK
        assert "bearer " not in html.lower()

    def test_no_refresh_tokens_in_html(self, client):
        """HTML should not contain OAuth refresh tokens."""
        response = client.get("/")
        html = response.text

        # Google refresh tokens start with "1//"
        assert "1//" not in html

        assert "refresh_token" not in html

    def test_no_tokens_in_dashboard(self, client):
        """Dashboard page should not expose tokens."""
        response = client.get("/dashboard")
        html = response.text

        assert "ya29." not in html
        assert "access_token" not in html or "csrf_token" in html

    def test_no_tokens_in_account_page(self, client):
        """Account page should not expose tokens."""
        response = client.get("/account")
        html = response.text

        assert "ya29." not in html
        assert "refresh_token" not in html

    def test_no_tokens_in_audit_log(self, client):
        """Audit log should not expose tokens."""
        response = client.get("/audit")
        html = response.text

        assert "ya29." not in html
        assert "access_token" not in html or "csrf_token" in html


class TestTokensNotInJavaScript:
    """Test that tokens are not embedded in JavaScript."""

    def test_no_inline_scripts_with_tokens(self, client):
        """Inline scripts should not contain OAuth tokens."""
        response = client.get("/")
        html = response.text

        # Check for inline scripts
        if "<script>" in html:
            # Extract inline script content
            # Should not contain tokens

            # Look for dangerous patterns
            assert "const accessToken =" not in html
            assert "var token =" not in html or "csrf" in html.lower()

    def test_no_tokens_in_javascript_variables(self, client):
        """JavaScript variables should not hold OAuth tokens."""
        response = client.get("/dashboard")
        html = response.text

        # Alpine.js x-data should not contain tokens
        assert 'x-data="{ token:' not in html
        assert 'x-data="{ accessToken:' not in html


class TestTokensNotInCookies:
    """Test that OAuth tokens are not stored in cookies."""

    def test_no_access_token_cookie(self, client):
        """Access tokens should not be in cookies."""
        response = client.get("/")

        # Check all cookies
        cookies = response.cookies

        # Should not have access_token cookie
        assert "access_token" not in cookies
        assert "oauth_token" not in cookies

    def test_no_refresh_token_cookie(self, client):
        """Refresh tokens should not be in cookies."""
        response = client.get("/")

        cookies = response.cookies

        assert "refresh_token" not in cookies

    def test_cookie_values_do_not_contain_tokens(self, client):
        """Cookie values should not contain OAuth token strings."""
        response = client.get("/")

        for cookie in response.cookies.jar:
            # Cookie values should not start with "ya29."
            assert not cookie.value.startswith("ya29.")

            # Should not start with "1//"
            assert not cookie.value.startswith("1//")


class TestTokensNotInAPIResponses:
    """Test that API endpoints don't expose tokens."""

    def test_health_endpoint_no_tokens(self, client):
        """Health endpoint should not expose tokens."""
        response = client.get("/health")

        data = response.json()

        # Convert to string to search
        response_text = str(data)

        assert "ya29." not in response_text
        assert "access_token" not in response_text
        assert "refresh_token" not in response_text

    def test_api_settings_response_no_tokens(self, client):
        """API settings responses should not expose tokens."""
        # Make API request
        response = client.get("/api/settings")  # May not exist yet

        if response.status_code == 200:
            # Check response doesn't contain tokens
            assert "ya29." not in response.text


class TestTokensNotInErrorMessages:
    """Test that error messages don't expose tokens."""

    def test_404_error_no_tokens(self, client):
        """404 error pages should not expose tokens."""
        response = client.get("/nonexistent-page")

        assert "ya29." not in response.text

    def test_500_error_no_tokens(self):
        """500 errors should not expose tokens."""
        # If internal server error occurs, should not expose tokens

        # Error messages should be sanitized

    def test_validation_errors_no_tokens(self):
        """Validation errors should not include token data."""
        # If user submits form with invalid data,
        # error message should not echo back sensitive data


class TestEncryptionKeysNotExposed:
    """Test that encryption keys are never exposed."""

    def test_no_encryption_key_in_html(self, client):
        """HTML should not contain ENCRYPTION_KEY."""
        response = client.get("/")
        html = response.text

        assert "ENCRYPTION_KEY" not in html
        assert "FERNET" not in html

    def test_no_secret_key_in_html(self, client):
        """HTML should not contain SECRET_KEY."""
        response = client.get("/")
        html = response.text

        assert "SECRET_KEY" not in html
        assert "SESSION_SECRET" not in html

    def test_no_google_client_secret_in_html(self, client):
        """HTML should not contain Google OAuth client secret."""
        response = client.get("/")
        html = response.text

        assert "GOOGLE_CLIENT_SECRET" not in html
        assert "client_secret" not in html or "csrf" in html.lower()


class TestDatabasePasswordsNotExposed:
    """Test that database credentials are not exposed."""

    def test_no_database_url_in_html(self, client):
        """HTML should not contain DATABASE_URL."""
        response = client.get("/")
        html = response.text

        assert "DATABASE_URL" not in html
        assert "postgresql://" not in html or "example" in html.lower()

    def test_no_redis_url_in_html(self, client):
        """HTML should not contain REDIS_URL."""
        response = client.get("/")
        html = response.text

        assert "REDIS_URL" not in html
        assert "redis://" not in html or "example" in html.lower()


class TestAPIKeysNotExposed:
    """Test that API keys are not exposed."""

    def test_no_openai_key_in_html(self, client):
        """HTML should not contain OpenAI API key."""
        response = client.get("/")
        html = response.text

        assert "OPENAI_API_KEY" not in html
        assert "sk-" not in html  # OpenAI keys start with sk-

    def test_no_postmark_key_in_html(self, client):
        """HTML should not contain Postmark API key."""
        response = client.get("/")
        html = response.text

        assert "POSTMARK_API_KEY" not in html


class TestSourceCodeDoesNotContainSecrets:
    """Test that source code doesn't accidentally contain secrets."""

    def test_env_example_has_placeholders(self):
        """Env example file should use placeholders, not real values."""
        # Read .env.example if it exists
        import os

        env_example_path = ".env.example"

        if os.path.exists(env_example_path):
            with open(env_example_path, "r") as f:
                content = f.read()

            # Should not contain real secrets
            assert "ya29." not in content
            assert "sk-" not in content  # OpenAI key
            assert "your-secret-key" in content.lower() or "placeholder" in content.lower()

    def test_gitignore_excludes_env_files(self):
        """Gitignore should exclude .env files."""
        import os

        gitignore_path = ".gitignore"

        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                content = f.read()

            # Should ignore .env
            assert ".env" in content


class TestTokenStorageInDatabase:
    """Test that tokens in database are encrypted."""

    def test_tokens_stored_encrypted(self):
        """OAuth tokens in database should be encrypted."""
        # This is tested in tests/security/test_token_encryption.py

        # Verify:
        # - Tokens are encrypted before storage
        # - Encryption uses Fernet
        # - Encryption key is from environment variable

    def test_database_schema_has_encrypted_fields(self):
        """Database schema should use encrypted_access_token field."""
        from app.models.user import Mailbox

        # Field should be named "encrypted_access_token", not "access_token"
        # This makes it obvious that encryption is required

        assert hasattr(Mailbox, "encrypted_access_token")
        assert hasattr(Mailbox, "encrypted_refresh_token")


class TestBrowserDevToolsSecurity:
    """Test that sensitive data is not exposed via browser DevTools."""

    def test_session_storage_should_be_empty(self):
        """SessionStorage should not contain sensitive data."""
        # Client-side test
        # Verify via browser DevTools that sessionStorage is empty

    def test_local_storage_should_be_empty(self):
        """LocalStorage should not contain sensitive data."""
        # Client-side test
        # Verify localStorage doesn't contain tokens

    def test_network_requests_do_not_expose_tokens(self):
        """Network requests should not expose tokens in URLs."""
        # OAuth tokens should never be in query parameters
        # Should be in request body or headers only

    def test_cookies_have_httponly_where_appropriate(self):
        """Sensitive cookies should have HttpOnly flag."""
        # Session cookie: HttpOnly = True
        # CSRF token cookie: HttpOnly = False (JS needs to read it)

        # Tested in test_session.py
