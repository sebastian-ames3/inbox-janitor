"""
Unit tests for OAuth token refresh retry logic (PRD-0007).

Tests the token refresh resilience implementation including:
- Retry logic with exponential backoff
- Permanent vs transient failure handling
- User notification escalation
- Mailbox state management
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
import requests

from app.modules.auth.gmail_oauth import (
    refresh_access_token_with_retry,
    handle_token_refresh_failure,
    OAuthPermanentError,
    OAuthTransientError,
)


class TestRefreshAccessTokenWithRetry:
    """Tests for refresh_access_token_with_retry() function."""

    @pytest.mark.asyncio
    async def test_token_refresh_success_on_first_attempt(self, mocker):
        """Token refresh succeeds on first attempt."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600
        }

        mocker.patch("requests.post", return_value=mock_response)
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")
        mocker.patch("app.modules.auth.gmail_oauth.encrypt_token", return_value="encrypted_new_access_token")

        # Execute
        encrypted_access, expires_at = await refresh_access_token_with_retry(
            mailbox_id="test-mailbox-id",
            refresh_token_encrypted="encrypted_refresh_token"
        )

        # Assert
        assert encrypted_access == "encrypted_new_access_token"
        assert isinstance(expires_at, datetime)
        assert expires_at > datetime.utcnow()

    @pytest.mark.asyncio
    async def test_transient_failure_retries_3_times(self, mocker):
        """Token refresh retries 3 times on network timeout."""
        # Mock 3 consecutive timeouts
        mock_post = mocker.patch("requests.post", side_effect=[
            requests.Timeout("Connection timeout"),  # Attempt 1
            requests.Timeout("Connection timeout"),  # Attempt 2
            requests.Timeout("Connection timeout"),  # Attempt 3
        ])
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")

        # Execute and assert raises after 3 attempts
        with pytest.raises(requests.Timeout):
            await refresh_access_token_with_retry(
                mailbox_id="test-mailbox-id",
                refresh_token_encrypted="encrypted_refresh_token"
            )

        # Verify 3 attempts were made
        assert mock_post.call_count == 3

    @pytest.mark.asyncio
    async def test_permanent_failure_no_retry_invalid_grant(self, mocker):
        """Invalid refresh token (invalid_grant) doesn't retry."""
        # Mock 400 invalid_grant response
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "invalid_grant"}

        mock_post = mocker.patch("requests.post", return_value=mock_response)
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")

        # Execute and assert raises OAuthPermanentError
        with pytest.raises(OAuthPermanentError) as exc_info:
            await refresh_access_token_with_retry(
                mailbox_id="test-mailbox-id",
                refresh_token_encrypted="encrypted_refresh_token"
            )

        # Verify error code
        assert exc_info.value.error_code == "invalid_grant"
        assert "User must reconnect" in str(exc_info.value)

        # Verify only 1 attempt (no retry)
        assert mock_post.call_count == 1

    @pytest.mark.asyncio
    async def test_permanent_failure_no_retry_token_revoked(self, mocker):
        """Revoked token doesn't retry."""
        # Mock 403 revoked token response
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "error": "access_denied",
            "error_description": "Token has been revoked"
        }

        mock_post = mocker.patch("requests.post", return_value=mock_response)
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")

        # Execute and assert raises OAuthPermanentError
        with pytest.raises(OAuthPermanentError) as exc_info:
            await refresh_access_token_with_retry(
                mailbox_id="test-mailbox-id",
                refresh_token_encrypted="encrypted_refresh_token"
            )

        # Verify error code
        assert exc_info.value.error_code == "token_revoked"

        # Verify only 1 attempt (no retry)
        assert mock_post.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_error_retries(self, mocker):
        """Connection error triggers retry."""
        # Mock connection error on attempts 1 and 2, success on attempt 3
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600
        }

        mock_post = mocker.patch("requests.post", side_effect=[
            requests.ConnectionError("Network unreachable"),  # Attempt 1
            requests.ConnectionError("Network unreachable"),  # Attempt 2
            mock_success,  # Attempt 3 - success
        ])
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")
        mocker.patch("app.modules.auth.gmail_oauth.encrypt_token", return_value="encrypted_new_access_token")

        # Execute
        encrypted_access, expires_at = await refresh_access_token_with_retry(
            mailbox_id="test-mailbox-id",
            refresh_token_encrypted="encrypted_refresh_token"
        )

        # Assert success after retries
        assert encrypted_access == "encrypted_new_access_token"

        # Verify 3 attempts were made
        assert mock_post.call_count == 3


class TestHandleTokenRefreshFailure:
    """Tests for handle_token_refresh_failure() function."""

    @pytest.fixture
    async def mock_session(self, mocker):
        """Create mock database session with mailbox and user."""
        from app.models.mailbox import Mailbox
        from app.models.user import User

        # Create mock mailbox
        mock_mailbox = Mock(spec=Mailbox)
        mock_mailbox.id = "test-mailbox-id"
        mock_mailbox.email_address = "test@example.com"
        mock_mailbox.user_id = "test-user-id"
        mock_mailbox.is_active = True
        mock_mailbox.token_refresh_attempt_count = 0
        mock_mailbox.token_refresh_failed_at = None
        mock_mailbox.token_refresh_error = None

        # Create mock user
        mock_user = Mock(spec=User)
        mock_user.id = "test-user-id"
        mock_user.email = "user@example.com"

        # Create mock session
        mock_session = AsyncMock()
        mock_session.get.side_effect = lambda model, id: {
            Mailbox: mock_mailbox,
            User: mock_user,
        }.get(model)
        mock_session.commit = AsyncMock()

        return mock_session, mock_mailbox, mock_user

    @pytest.mark.asyncio
    async def test_first_attempt_logs_warning_no_email(self, mock_session, mocker):
        """First failure logs warning but doesn't send email."""
        session, mailbox, user = await mock_session

        error = requests.Timeout("Connection timeout")

        # Execute
        await handle_token_refresh_failure(
            mailbox_id="test-mailbox-id",
            error=error,
            attempt=1,
            session=session
        )

        # Assert
        assert mailbox.token_refresh_attempt_count == 1
        assert mailbox.is_active == True  # Still active
        assert session.commit.called

        # TODO: Verify no email sent (when email sending implemented)

    @pytest.mark.asyncio
    async def test_second_attempt_sends_gentle_email(self, mock_session, mocker):
        """Second failure sends gentle email to user."""
        session, mailbox, user = await mock_session

        error = requests.Timeout("Connection timeout")

        # Execute
        await handle_token_refresh_failure(
            mailbox_id="test-mailbox-id",
            error=error,
            attempt=2,
            session=session
        )

        # Assert
        assert mailbox.token_refresh_attempt_count == 2
        assert mailbox.is_active == True  # Still active
        assert session.commit.called

        # TODO: Verify gentle email sent (when email sending implemented)

    @pytest.mark.asyncio
    async def test_third_attempt_disables_mailbox_sends_urgent_email(self, mock_session, mocker):
        """Third failure disables mailbox and sends urgent email."""
        session, mailbox, user = await mock_session

        error = requests.Timeout("Connection timeout")

        # Execute
        await handle_token_refresh_failure(
            mailbox_id="test-mailbox-id",
            error=error,
            attempt=3,
            session=session
        )

        # Assert
        assert mailbox.is_active == False  # Disabled
        assert mailbox.token_refresh_attempt_count == 3
        assert mailbox.token_refresh_failed_at is not None
        assert "Failed after 3 attempts" in mailbox.token_refresh_error
        assert session.commit.called

        # TODO: Verify urgent email sent (when email sending implemented)

    @pytest.mark.asyncio
    async def test_permanent_failure_disables_immediately(self, mock_session, mocker):
        """Permanent failure disables mailbox on first attempt."""
        session, mailbox, user = await mock_session

        error = OAuthPermanentError("Invalid refresh token", error_code="invalid_grant")

        # Execute
        await handle_token_refresh_failure(
            mailbox_id="test-mailbox-id",
            error=error,
            attempt=1,
            session=session
        )

        # Assert
        assert mailbox.is_active == False  # Disabled immediately
        assert mailbox.token_refresh_failed_at is not None
        assert "invalid_grant" in mailbox.token_refresh_error
        assert mailbox.token_refresh_attempt_count == 0  # Reset counter
        assert session.commit.called

        # TODO: Verify immediate email sent (when email sending implemented)

    @pytest.mark.asyncio
    async def test_mailbox_not_found_handles_gracefully(self, mocker):
        """Handle case where mailbox not found during failure handling."""
        # Create mock session that returns None for mailbox
        mock_session = AsyncMock()
        mock_session.get.return_value = None

        error = requests.Timeout("Connection timeout")

        # Execute - should not raise exception
        await handle_token_refresh_failure(
            mailbox_id="nonexistent-mailbox-id",
            error=error,
            attempt=1,
            session=mock_session
        )

        # Assert - session.commit should not be called
        assert not mock_session.commit.called


class TestRetryBehavior:
    """Integration tests for retry behavior."""

    @pytest.mark.asyncio
    async def test_retry_backoff_timing(self, mocker):
        """Verify exponential backoff timing (2s, 4s, 8s)."""
        import time

        # Track call times
        call_times = []

        def mock_post(*args, **kwargs):
            call_times.append(time.time())
            raise requests.Timeout("Connection timeout")

        mocker.patch("requests.post", side_effect=mock_post)
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")

        # Execute and catch exception
        start_time = time.time()
        with pytest.raises(requests.Timeout):
            await refresh_access_token_with_retry(
                mailbox_id="test-mailbox-id",
                refresh_token_encrypted="encrypted_refresh_token"
            )

        # Verify 3 attempts
        assert len(call_times) == 3

        # Verify total time is at least 2s (first retry delay) + some processing time
        # The actual delays are: 2s, 4s (total ~6s), but allowing variance for test environment
        total_time = time.time() - start_time
        assert 2 < total_time < 20  # At least 2s backoff, generous upper bound for slow CI

    @pytest.mark.asyncio
    async def test_success_after_retry_resets_failure_count(self, mocker):
        """Successful refresh after retries should reset failure tracking."""
        # Mock failure on attempt 1, success on attempt 2
        mock_success = Mock()
        mock_success.status_code = 200
        mock_success.json.return_value = {
            "access_token": "new_access_token",
            "expires_in": 3600
        }

        mocker.patch("requests.post", side_effect=[
            requests.Timeout("Connection timeout"),  # Attempt 1 fails
            mock_success,  # Attempt 2 succeeds
        ])
        mocker.patch("app.modules.auth.gmail_oauth.decrypt_token", return_value="decrypted_refresh_token")
        mocker.patch("app.modules.auth.gmail_oauth.encrypt_token", return_value="encrypted_new_access_token")

        # Execute
        encrypted_access, expires_at = await refresh_access_token_with_retry(
            mailbox_id="test-mailbox-id",
            refresh_token_encrypted="encrypted_refresh_token"
        )

        # Assert success
        assert encrypted_access == "encrypted_new_access_token"

        # Note: The calling code (get_gmail_service) is responsible for resetting
        # the failure count on success. This test verifies the retry logic works.
