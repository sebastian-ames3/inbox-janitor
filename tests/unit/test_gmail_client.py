"""
Unit tests for GmailClient.

Tests Gmail API integration with mocked responses:
- Email fetching (list_messages, get_message)
- Email actions (trash, untrash, modify)
- Label management
- Error handling (401, 403, 429, 500/503)
- Retry logic with exponential backoff
- Rate limiting integration
- Security: format='metadata' enforcement

Run tests:
    pytest tests/unit/test_gmail_client.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError
import httplib2

from app.modules.ingest.gmail_client import (
    GmailClient,
    GmailAPIError,
    GmailQuotaExceeded,
    GmailAuthError,
)
from app.models.mailbox import Mailbox


# Test fixtures

@pytest.fixture
def mock_mailbox():
    """Create a mock mailbox for testing."""
    mailbox = Mock(spec=Mailbox)
    mailbox.id = "test-mailbox-id"
    mailbox.user_id = "test-user-id"
    mailbox.provider = "gmail"
    mailbox.email_address = "test@example.com"
    mailbox.is_active = True
    mailbox.encrypted_access_token = "encrypted_token"
    mailbox.encrypted_refresh_token = "encrypted_refresh_token"
    return mailbox


@pytest.fixture
def mock_gmail_service():
    """Create a mock Gmail API service."""
    service = MagicMock()
    return service


@pytest.fixture
def mock_rate_limiter():
    """Create a mock rate limiter that always allows requests."""
    limiter = AsyncMock()
    limiter.check_and_increment = AsyncMock()
    return limiter


def create_http_error(status_code: int, reason: str = "Error"):
    """Create a mock HttpError for testing."""
    resp = httplib2.Response({"status": status_code})
    content = f'{{"error": {{"message": "{reason}"}}}}'.encode()
    return HttpError(resp, content)


# Test GmailClient initialization

class TestGmailClientInit:
    """Test GmailClient initialization and validation."""

    def test_init_with_valid_mailbox(self, mock_mailbox):
        """Test initialization with valid mailbox."""
        client = GmailClient(mock_mailbox)
        assert client.mailbox == mock_mailbox
        assert client._service is None
        assert client._max_retries == 3

    def test_init_with_custom_max_retries(self, mock_mailbox):
        """Test initialization with custom max_retries."""
        client = GmailClient(mock_mailbox, max_retries=5)
        assert client._max_retries == 5

    def test_init_with_none_mailbox(self):
        """Test initialization with None mailbox raises ValueError."""
        with pytest.raises(ValueError, match="Mailbox is required"):
            GmailClient(None)

    def test_init_with_inactive_mailbox(self, mock_mailbox):
        """Test initialization with inactive mailbox raises ValueError."""
        mock_mailbox.is_active = False
        with pytest.raises(ValueError, match="inactive"):
            GmailClient(mock_mailbox)

    def test_init_with_non_gmail_provider(self, mock_mailbox):
        """Test initialization with non-Gmail provider raises ValueError."""
        mock_mailbox.provider = "microsoft365"
        with pytest.raises(ValueError, match="not a Gmail account"):
            GmailClient(mock_mailbox)


# Test list_messages

class TestListMessages:
    """Test list_messages method."""

    @pytest.mark.asyncio
    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    async def test_list_messages_basic(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test basic list_messages call."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "messages": [
                {"id": "msg1", "threadId": "thread1"},
                {"id": "msg2", "threadId": "thread2"},
            ],
            "resultSizeEstimate": 2
        }
        mock_service.users().messages().list().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = await client.list_messages(query="in:inbox", max_results=100)

        # Verify
        assert result == mock_response
        assert len(result["messages"]) == 2
        # Verify list was called (don't check call count due to mock chaining)
        assert mock_service.users().messages().list().execute.called

    @pytest.mark.asyncio
    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    async def test_list_messages_with_pagination(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test list_messages with page_token."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "messages": [{"id": "msg3", "threadId": "thread3"}],
            "nextPageToken": "next_token_123"
        }
        mock_service.users().messages().list().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = await client.list_messages(page_token="prev_token_abc")

        # Verify
        assert result["nextPageToken"] == "next_token_123"

    @pytest.mark.asyncio
    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    async def test_list_messages_with_label_ids(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test list_messages with label_ids filter."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {"messages": [], "resultSizeEstimate": 0}
        mock_service.users().messages().list().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = await client.list_messages(label_ids=["INBOX", "CATEGORY_PROMOTIONS"])

        # Verify
        assert result["resultSizeEstimate"] == 0


# Test get_message

class TestGetMessage:
    """Test get_message method."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_get_message_with_metadata_format(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test get_message with format='metadata'."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "id": "msg123",
            "threadId": "thread123",
            "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"],
            "snippet": "This is a test email snippet...",
            "payload": {
                "headers": [
                    {"name": "From", "value": "sender@example.com"},
                    {"name": "Subject", "value": "Test Subject"},
                ]
            }
        }
        mock_service.users().messages().get().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.get_message(message_id="msg123", format="metadata")

        # Verify
        assert result["id"] == "msg123"
        assert result["snippet"] == "This is a test email snippet..."

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_get_message_with_minimal_format(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test get_message with format='minimal'."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {"id": "msg123", "threadId": "thread123"}
        mock_service.users().messages().get().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.get_message(message_id="msg123", format="minimal")

        # Verify
        assert result["id"] == "msg123"

    def test_get_message_with_full_format_raises_error(self, mock_mailbox):
        """Test get_message with format='full' raises ValueError (security check)."""
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)

        with pytest.raises(ValueError, match="Invalid format 'full'"):
            client.get_message(message_id="msg123", format="full")


# Test trash_message

class TestTrashMessage:
    """Test trash_message method."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_trash_message_success(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test successful trash_message call."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "id": "msg123",
            "labelIds": ["TRASH"]
        }
        mock_service.users().messages().trash().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.trash_message(message_id="msg123")

        # Verify
        assert result["id"] == "msg123"
        assert "TRASH" in result["labelIds"]
        assert mock_service.users().messages().trash().execute.called


# Test untrash_message

class TestUntrashMessage:
    """Test untrash_message method."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_untrash_message_success(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test successful untrash_message call."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "id": "msg123",
            "labelIds": ["INBOX"]
        }
        mock_service.users().messages().untrash().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.untrash_message(message_id="msg123")

        # Verify
        assert result["id"] == "msg123"
        assert "INBOX" in result["labelIds"]
        assert mock_service.users().messages().untrash().execute.called


# Test modify_message

class TestModifyMessage:
    """Test modify_message method."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_modify_message_remove_inbox(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test modify_message to remove INBOX label (archive)."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "id": "msg123",
            "labelIds": ["CATEGORY_PROMOTIONS"]
        }
        mock_service.users().messages().modify().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.modify_message(message_id="msg123", remove_label_ids=["INBOX"])

        # Verify
        assert result["id"] == "msg123"
        assert "INBOX" not in result["labelIds"]

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_modify_message_add_label(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test modify_message to add custom label."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "id": "msg123",
            "labelIds": ["INBOX", "Label_123"]
        }
        mock_service.users().messages().modify().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.modify_message(message_id="msg123", add_label_ids=["Label_123"])

        # Verify
        assert "Label_123" in result["labelIds"]


# Test get_labels

class TestGetLabels:
    """Test get_labels method."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_get_labels_success(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test successful get_labels call."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "labels": [
                {"id": "INBOX", "name": "INBOX", "type": "system"},
                {"id": "Label_1", "name": "Receipts", "type": "user"},
            ]
        }
        mock_service.users().labels().list().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.get_labels()

        # Verify
        assert len(result) == 2
        assert result[0]["name"] == "INBOX"
        assert result[1]["name"] == "Receipts"


# Test create_label

class TestCreateLabel:
    """Test create_label method."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_create_label_success(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test successful create_label call."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {
            "id": "Label_123",
            "name": "Receipts",
            "type": "user"
        }
        mock_service.users().labels().create().execute.return_value = mock_response

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)
        result = client.create_label(name="Receipts")

        # Verify
        assert result["id"] == "Label_123"
        assert result["name"] == "Receipts"


# Test error handling

class TestErrorHandling:
    """Test error handling and retry logic."""

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_401_error_triggers_token_refresh(self, mock_sleep, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test 401 error triggers service rebuild (token refresh)."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # First call returns 401, second call succeeds
        mock_service.users().messages().list().execute.side_effect = [
            create_http_error(401, "Unauthorized"),
            {"messages": [], "resultSizeEstimate": 0}
        ]

        # Execute
        client = GmailClient(mock_mailbox, max_retries=3)
        result = client.list_messages()

        # Verify - should retry and succeed
        assert result["resultSizeEstimate"] == 0
        assert mock_service.users().messages().list().execute.call_count == 2

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_403_error_raises_auth_error(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test 403 error raises GmailAuthError."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.users().messages().list().execute.side_effect = create_http_error(403, "Forbidden")

        # Execute & Verify
        client = GmailClient(mock_mailbox, max_retries=1)
        with pytest.raises(GmailAuthError, match="Access forbidden"):
            client.list_messages()

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    @patch("time.sleep")
    def test_429_error_retries_with_exponential_backoff(self, mock_sleep, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test 429 error retries with exponential backoff."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # First two calls return 429, third succeeds
        mock_service.users().messages().list().execute.side_effect = [
            create_http_error(429, "Quota exceeded"),
            create_http_error(429, "Quota exceeded"),
            {"messages": [], "resultSizeEstimate": 0}
        ]

        # Execute
        client = GmailClient(mock_mailbox, max_retries=3)
        result = client.list_messages()

        # Verify
        assert result["resultSizeEstimate"] == 0
        assert mock_service.users().messages().list().execute.call_count == 3
        # Check exponential backoff: 1s, 2s
        assert mock_sleep.call_count >= 2

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_429_error_max_retries_raises_quota_exceeded(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test 429 error after max retries raises GmailQuotaExceeded."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.users().messages().list().execute.side_effect = create_http_error(429, "Quota exceeded")

        # Execute & Verify
        client = GmailClient(mock_mailbox, max_retries=2)
        with pytest.raises(GmailQuotaExceeded):
            client.list_messages()

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    @patch("time.sleep")
    def test_500_error_retries(self, mock_sleep, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test 500 server error retries."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # First call returns 500, second succeeds
        mock_service.users().messages().list().execute.side_effect = [
            create_http_error(500, "Internal Server Error"),
            {"messages": [], "resultSizeEstimate": 0}
        ]

        # Execute
        client = GmailClient(mock_mailbox, max_retries=3)
        result = client.list_messages()

        # Verify
        assert result["resultSizeEstimate"] == 0
        assert mock_service.users().messages().list().execute.call_count == 2

    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    def test_404_error_raises_api_error(self, mock_build, mock_decrypt, mock_mailbox, mock_rate_limiter):
        """Test 404 error raises GmailAPIError."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_service.users().messages().get().execute.side_effect = create_http_error(404, "Not Found")

        # Execute & Verify
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter, max_retries=1)
        with pytest.raises(GmailAPIError, match="Resource not found"):
            client.get_message(message_id="nonexistent")


# Test rate limiting (CRITICAL - PRD-0004)

class TestRateLimiting:
    """Test rate limiting enforcement (no bypass)."""

    @pytest.mark.asyncio
    @patch("app.modules.ingest.gmail_client.decrypt_token")
    @patch("app.modules.ingest.gmail_client.build")
    async def test_rate_limit_enforced_in_all_contexts(self, mock_build, mock_decrypt, mock_mailbox):
        """Verify rate limiter is called in all contexts (no bypass)."""
        # Setup
        mock_decrypt.return_value = "plaintext_token"
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        mock_response = {"messages": [], "resultSizeEstimate": 0}
        mock_service.users().messages().list().execute.return_value = mock_response

        # Create mock rate limiter to track calls
        mock_limiter = AsyncMock()
        mock_limiter.check_and_increment = AsyncMock()

        # Execute
        client = GmailClient(mock_mailbox, rate_limiter=mock_limiter)
        await client.list_messages(query="in:inbox")

        # Verify rate limiter was called
        assert mock_limiter.check_and_increment.called
        assert mock_limiter.check_and_increment.call_count == 1
        mock_limiter.check_and_increment.assert_called_with(
            user_id=str(mock_mailbox.user_id),
            quota_units=5
        )

    @pytest.mark.asyncio
    async def test_gmail_client_requires_await(self, mock_mailbox, mock_rate_limiter):
        """GmailClient methods must be awaited (not called synchronously)."""
        client = GmailClient(mock_mailbox, rate_limiter=mock_rate_limiter)

        # Calling without await returns a coroutine, not a result
        result = client.list_messages()

        # Verify it's a coroutine (not a dict)
        import inspect
        assert inspect.iscoroutine(result)

        # Clean up the coroutine to avoid warnings
        result.close()
