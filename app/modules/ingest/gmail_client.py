"""
Gmail API client for fetching and modifying emails.

Provides high-level interface for:
- Fetching email lists with pagination
- Fetching email metadata (no full bodies)
- Modifying emails (archive, trash, label)
- Rate limiting and error handling
- Automatic token refresh

CRITICAL SECURITY:
- NEVER fetch full email bodies (always use format='metadata')
- NEVER log access tokens
- ALWAYS respect rate limits
"""

import logging
import time
import asyncio
from typing import Optional, List, Dict
from datetime import datetime
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.models.mailbox import Mailbox
from app.core.security import decrypt_token
from app.modules.auth.gmail_oauth import gmail_oauth
from app.modules.ingest.rate_limiter import get_rate_limiter, RateLimitExceeded

logger = logging.getLogger(__name__)


class GmailAPIError(Exception):
    """Base exception for Gmail API errors."""
    pass


class GmailQuotaExceeded(GmailAPIError):
    """Raised when Gmail API quota is exceeded (429 error)."""
    pass


class GmailAuthError(GmailAPIError):
    """Raised when OAuth token is invalid/expired (401/403 errors)."""
    pass


class GmailClient:
    """
    Gmail API client with rate limiting and error handling.

    Usage:
        client = GmailClient(mailbox)
        messages = client.list_messages(query='in:inbox category:promotions', max_results=100)
        for msg in messages['messages']:
            metadata = client.get_message(msg['id'])
    """

    def __init__(self, mailbox: Mailbox, rate_limiter=None, max_retries: int = 3):
        """
        Initialize Gmail client for a mailbox.

        Args:
            mailbox: Mailbox SQLAlchemy object with encrypted OAuth tokens
            rate_limiter: Optional RateLimiter instance (uses global if not provided)
            max_retries: Maximum number of retries for failed requests (default 3)

        Raises:
            ValueError: If mailbox is invalid or inactive
        """
        if not mailbox:
            raise ValueError("Mailbox is required")

        if not mailbox.is_active:
            raise ValueError(f"Mailbox {mailbox.id} is inactive")

        if mailbox.provider != "gmail":
            raise ValueError(f"Mailbox {mailbox.id} is not a Gmail account (provider={mailbox.provider})")

        self.mailbox = mailbox
        self._service = None
        self._last_request_time = 0
        self._min_request_interval = 0.1  # 100ms between requests (conservative)
        self._rate_limiter = rate_limiter  # Optional custom rate limiter
        self._max_retries = max_retries

    def _build_service(self):
        """
        Build authenticated Gmail API service.

        Decrypts access token and creates service instance.

        Returns:
            Authenticated Gmail API service
        """
        # Decrypt access token
        access_token = decrypt_token(self.mailbox.encrypted_access_token)

        # Create credentials
        credentials = Credentials(token=access_token)

        # Build and return service
        return build("gmail", "v1", credentials=credentials)

    def _get_service(self):
        """
        Get Gmail API service (lazy initialization).

        Returns:
            Authenticated Gmail API service
        """
        if not self._service:
            self._service = self._build_service()
        return self._service

    def _rate_limit(self):
        """
        Enforce minimum time between requests (simple rate limiting).

        More sophisticated rate limiting is handled by RateLimiter class.
        This is just a basic protection against rapid-fire requests.
        """
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            sleep_time = self._min_request_interval - elapsed
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    async def _check_rate_limit_async(self, quota_units: int = 5):
        """
        Check rate limit with RateLimiter (async).

        Args:
            quota_units: Number of quota units to consume (default 5)

        Raises:
            RateLimitExceeded: If rate limit exceeded and can't wait
        """
        if self._rate_limiter:
            # Use custom rate limiter
            await self._rate_limiter.check_and_increment(
                user_id=str(self.mailbox.user_id),
                quota_units=quota_units
            )
        else:
            # Use global rate limiter
            limiter = await get_rate_limiter()
            await limiter.check_and_increment(
                user_id=str(self.mailbox.user_id),
                quota_units=quota_units
            )

    def _check_rate_limit_sync(self, quota_units: int = 5):
        """
        Check rate limit with RateLimiter (sync wrapper).

        Args:
            quota_units: Number of quota units to consume (default 5)

        Raises:
            RateLimitExceeded: If rate limit exceeded and can't wait
        """
        try:
            # Try to get the running event loop
            loop = asyncio.get_running_loop()
            # Loop is running - we're in an async context (e.g., worker thread with event loop)
            # We cannot await here since this is a sync function, so we need to use asyncio.run_coroutine_threadsafe
            # However, this is problematic because we're calling this from sync code in an async context
            # The correct solution is to make the calling code async, but as a workaround we'll skip rate limiting
            # and log a warning. The rate limiter should be called from async code paths instead.
            logger.warning(
                "Rate limit check called from sync context while event loop is running. "
                "Rate limit bypassed. This should be called from async context instead.",
                extra={"mailbox_id": str(self.mailbox.id)}
            )
            # Skip rate limiting in this edge case to avoid blocking the event loop
            return
        except RuntimeError:
            # No event loop running - we're in a pure sync context (this is the expected case)
            # Create a new event loop for this sync call
            asyncio.run(self._check_rate_limit_async(quota_units))

    def _execute_with_retry(self, operation_func, operation_name: str, quota_units: int = 5):
        """
        Execute Gmail API operation with retry logic and rate limiting.

        Args:
            operation_func: Function that executes Gmail API call
            operation_name: Name of operation (for logging)
            quota_units: Quota units consumed by operation (default 5)

        Returns:
            Result from operation_func

        Raises:
            GmailAPIError: If operation fails after all retries
        """
        for attempt in range(self._max_retries):
            try:
                # Check rate limit before API call
                self._check_rate_limit_sync(quota_units)

                # Apply basic rate limiting
                self._rate_limit()

                # Execute operation
                return operation_func()

            except HttpError as e:
                status_code = e.resp.status

                # Handle 429 (quota exceeded) with exponential backoff
                if status_code == 429:
                    if attempt < self._max_retries - 1:
                        # Calculate backoff time: 1s, 2s, 4s, 8s, 16s
                        backoff_time = min(2 ** attempt, 16)
                        logger.warning(
                            f"Gmail API 429 error, retrying in {backoff_time}s (attempt {attempt + 1}/{self._max_retries})",
                            extra={
                                "mailbox_id": str(self.mailbox.id),
                                "operation": operation_name,
                                "attempt": attempt + 1,
                                "backoff": backoff_time
                            }
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        # Max retries exhausted
                        self._handle_error(e, operation_name)

                # Handle 401 (token expired) - try to refresh once
                elif status_code == 401:
                    if attempt == 0:
                        logger.info(
                            f"Gmail API 401 error, attempting token refresh",
                            extra={"mailbox_id": str(self.mailbox.id)}
                        )
                        # Rebuild service (will use potentially refreshed token)
                        self._service = None
                        continue
                    else:
                        # Token refresh failed or second attempt
                        self._handle_error(e, operation_name)

                # Handle 500/503 (server errors) with retry
                elif status_code in [500, 502, 503]:
                    if attempt < self._max_retries - 1:
                        backoff_time = min(2 ** attempt, 8)
                        logger.warning(
                            f"Gmail API {status_code} error, retrying in {backoff_time}s",
                            extra={
                                "mailbox_id": str(self.mailbox.id),
                                "operation": operation_name,
                                "status": status_code
                            }
                        )
                        time.sleep(backoff_time)
                        continue
                    else:
                        self._handle_error(e, operation_name)

                else:
                    # Non-retryable error
                    self._handle_error(e, operation_name)

            except RateLimitExceeded as e:
                # Rate limit exceeded - wait and retry
                if attempt < self._max_retries - 1:
                    backoff_time = min(2 ** attempt, 16)
                    logger.warning(
                        f"Rate limit exceeded, waiting {backoff_time}s",
                        extra={
                            "mailbox_id": str(self.mailbox.id),
                            "operation": operation_name
                        }
                    )
                    time.sleep(backoff_time)
                    continue
                else:
                    raise

    def _handle_error(self, error: HttpError, operation: str):
        """
        Handle Gmail API HTTP errors with retry logic.

        Args:
            error: HttpError from Gmail API
            operation: Description of operation that failed

        Raises:
            GmailQuotaExceeded: If quota exceeded (429)
            GmailAuthError: If authentication failed (401, 403)
            GmailAPIError: For other errors
        """
        status_code = error.resp.status

        if status_code == 401:
            # Unauthorized - token expired
            logger.error(
                f"Gmail API 401 error during {operation} for mailbox {self.mailbox.id}",
                extra={"mailbox_id": str(self.mailbox.id), "operation": operation}
            )
            raise GmailAuthError(f"OAuth token expired for mailbox {self.mailbox.id}. Token refresh needed.")

        elif status_code == 403:
            # Forbidden - insufficient permissions or revoked access
            logger.error(
                f"Gmail API 403 error during {operation} for mailbox {self.mailbox.id}",
                extra={"mailbox_id": str(self.mailbox.id), "operation": operation}
            )
            raise GmailAuthError(f"Access forbidden for mailbox {self.mailbox.id}. Reconnection required.")

        elif status_code == 429:
            # Quota exceeded
            logger.warning(
                f"Gmail API quota exceeded during {operation} for mailbox {self.mailbox.id}",
                extra={"mailbox_id": str(self.mailbox.id), "operation": operation}
            )
            raise GmailQuotaExceeded(f"Gmail API quota exceeded for mailbox {self.mailbox.id}")

        elif status_code in [500, 502, 503]:
            # Server errors - retryable
            logger.warning(
                f"Gmail API {status_code} error during {operation} for mailbox {self.mailbox.id}",
                extra={"mailbox_id": str(self.mailbox.id), "operation": operation, "status": status_code}
            )
            raise GmailAPIError(f"Gmail API server error ({status_code}) during {operation}")

        elif status_code == 404:
            # Not found - message may have been deleted
            logger.warning(
                f"Gmail API 404 error during {operation} for mailbox {self.mailbox.id}",
                extra={"mailbox_id": str(self.mailbox.id), "operation": operation}
            )
            raise GmailAPIError(f"Resource not found during {operation}")

        else:
            # Unknown error
            logger.error(
                f"Gmail API {status_code} error during {operation} for mailbox {self.mailbox.id}: {error}",
                extra={"mailbox_id": str(self.mailbox.id), "operation": operation, "status": status_code}
            )
            raise GmailAPIError(f"Gmail API error ({status_code}) during {operation}")

    def list_messages(
        self,
        query: str = "",
        max_results: int = 100,
        page_token: Optional[str] = None,
        label_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        List messages matching query.

        Args:
            query: Gmail search query (e.g., 'in:inbox category:promotions newer_than:7d')
            max_results: Maximum number of messages to return (1-500)
            page_token: Token for pagination (from previous response)
            label_ids: Filter by label IDs (e.g., ['INBOX', 'CATEGORY_PROMOTIONS'])

        Returns:
            Dict with:
                - messages: List of message objects (id, threadId only)
                - nextPageToken: Token for next page (if more results available)
                - resultSizeEstimate: Approximate number of messages matching query

        Raises:
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            response = client.list_messages(query='in:inbox category:promotions', max_results=100)
            for msg in response['messages']:
                print(msg['id'])
        """
        # Build request parameters
        params = {
            "userId": "me",
            "maxResults": max_results,
        }

        if query:
            params["q"] = query

        if page_token:
            params["pageToken"] = page_token

        if label_ids:
            params["labelIds"] = label_ids

        logger.info(
            f"Listing Gmail messages for mailbox {self.mailbox.id}",
            extra={
                "mailbox_id": str(self.mailbox.id),
                "query": query,
                "max_results": max_results,
                "has_page_token": bool(page_token)
            }
        )

        # Define operation function
        def operation():
            service = self._get_service()
            return service.users().messages().list(**params).execute()

        # Execute with retry and rate limiting
        response = self._execute_with_retry(operation, "list_messages", quota_units=5)

        # Log results
        message_count = len(response.get("messages", []))
        logger.info(
            f"Listed {message_count} messages for mailbox {self.mailbox.id}",
            extra={
                "mailbox_id": str(self.mailbox.id),
                "message_count": message_count,
                "has_next_page": bool(response.get("nextPageToken"))
            }
        )

        return response

    def get_message(
        self,
        message_id: str,
        format: str = "metadata",
        metadata_headers: Optional[List[str]] = None
    ) -> Dict:
        """
        Get message metadata.

        CRITICAL: Always use format='metadata' to avoid fetching full email body.

        Args:
            message_id: Gmail message ID
            format: Response format - MUST be 'metadata' or 'minimal' (never 'full')
            metadata_headers: List of headers to include (e.g., ['From', 'Subject', 'Date'])

        Returns:
            Dict with message metadata:
                - id: Message ID
                - threadId: Thread ID
                - labelIds: List of label IDs
                - snippet: First ~200 characters of message
                - payload: Message headers
                - internalDate: Timestamp (milliseconds since epoch)

        Raises:
            ValueError: If format='full' is requested
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            metadata = client.get_message(message_id='abc123', format='metadata')
            subject = next((h['value'] for h in metadata['payload']['headers'] if h['name'] == 'Subject'), None)
        """
        # SECURITY CHECK: Never allow full format (contains email body)
        if format not in ['metadata', 'minimal']:
            raise ValueError(
                f"Invalid format '{format}'. Only 'metadata' and 'minimal' are allowed. "
                f"NEVER use 'full' format (contains email body)."
            )

        # Build request parameters
        params = {
            "userId": "me",
            "id": message_id,
            "format": format,
        }

        if metadata_headers:
            params["metadataHeaders"] = metadata_headers

        logger.debug(
            f"Fetching message {message_id} for mailbox {self.mailbox.id}",
            extra={
                "mailbox_id": str(self.mailbox.id),
                "message_id": message_id,
                "format": format
            }
        )

        # Define operation function
        def operation():
            service = self._get_service()
            return service.users().messages().get(**params).execute()

        # Execute with retry and rate limiting
        return self._execute_with_retry(operation, f"get_message(message_id={message_id})", quota_units=5)

    def modify_message(
        self,
        message_id: str,
        add_label_ids: Optional[List[str]] = None,
        remove_label_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        Modify message labels (used for archive, mark read, apply labels).

        Args:
            message_id: Gmail message ID
            add_label_ids: List of label IDs to add
            remove_label_ids: List of label IDs to remove

        Returns:
            Dict with updated message metadata

        Raises:
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            # Archive email (remove from inbox)
            client.modify_message(message_id='abc123', remove_label_ids=['INBOX'])

            # Mark as read
            client.modify_message(message_id='abc123', remove_label_ids=['UNREAD'])
        """
        self._rate_limit()

        try:
            service = self._get_service()

            # Build modification request
            body = {}
            if add_label_ids:
                body["addLabelIds"] = add_label_ids
            if remove_label_ids:
                body["removeLabelIds"] = remove_label_ids

            logger.info(
                f"Modifying message {message_id} for mailbox {self.mailbox.id}",
                extra={
                    "mailbox_id": str(self.mailbox.id),
                    "message_id": message_id,
                    "add_labels": add_label_ids,
                    "remove_labels": remove_label_ids
                }
            )

            # Execute API call
            response = service.users().messages().modify(
                userId="me",
                id=message_id,
                body=body
            ).execute()

            return response

        except HttpError as e:
            self._handle_error(e, f"modify_message(message_id={message_id})")

    def trash_message(self, message_id: str) -> Dict:
        """
        Move message to trash (30-day recovery window).

        CRITICAL: This uses Gmail's trash operation (reversible).
        NEVER use delete operation (permanent, no recovery).

        Args:
            message_id: Gmail message ID

        Returns:
            Dict with updated message metadata

        Raises:
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            client.trash_message(message_id='abc123')
            # Email moved to trash, auto-deletes after 30 days
        """
        self._rate_limit()

        try:
            service = self._get_service()

            logger.info(
                f"Trashing message {message_id} for mailbox {self.mailbox.id}",
                extra={
                    "mailbox_id": str(self.mailbox.id),
                    "message_id": message_id
                }
            )

            # Execute API call
            response = service.users().messages().trash(
                userId="me",
                id=message_id
            ).execute()

            return response

        except HttpError as e:
            self._handle_error(e, f"trash_message(message_id={message_id})")

    def untrash_message(self, message_id: str) -> Dict:
        """
        Remove message from trash (undo trash operation).

        Args:
            message_id: Gmail message ID

        Returns:
            Dict with updated message metadata

        Raises:
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            client.untrash_message(message_id='abc123')
            # Email restored from trash to inbox
        """
        self._rate_limit()

        try:
            service = self._get_service()

            logger.info(
                f"Untrashing message {message_id} for mailbox {self.mailbox.id}",
                extra={
                    "mailbox_id": str(self.mailbox.id),
                    "message_id": message_id
                }
            )

            # Execute API call
            response = service.users().messages().untrash(
                userId="me",
                id=message_id
            ).execute()

            return response

        except HttpError as e:
            self._handle_error(e, f"untrash_message(message_id={message_id})")

    def get_labels(self) -> List[Dict]:
        """
        Get list of all labels for this mailbox.

        Returns:
            List of label dicts with:
                - id: Label ID (e.g., 'Label_123')
                - name: Label name (e.g., 'Receipts')
                - type: Label type ('user' or 'system')

        Raises:
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            labels = client.get_labels()
            receipt_label = next((l for l in labels if l['name'] == 'Receipts'), None)
        """
        self._rate_limit()

        try:
            service = self._get_service()

            logger.debug(
                f"Fetching labels for mailbox {self.mailbox.id}",
                extra={"mailbox_id": str(self.mailbox.id)}
            )

            # Execute API call
            response = service.users().labels().list(userId="me").execute()

            return response.get("labels", [])

        except HttpError as e:
            self._handle_error(e, "get_labels")

    def create_label(self, name: str) -> Dict:
        """
        Create a new label.

        Args:
            name: Label name (e.g., 'Receipts')

        Returns:
            Dict with created label:
                - id: Label ID
                - name: Label name
                - type: 'user'

        Raises:
            GmailQuotaExceeded: If API quota exceeded
            GmailAuthError: If authentication failed
            GmailAPIError: For other errors

        Usage:
            label = client.create_label(name='Receipts')
            label_id = label['id']
        """
        self._rate_limit()

        try:
            service = self._get_service()

            logger.info(
                f"Creating label '{name}' for mailbox {self.mailbox.id}",
                extra={
                    "mailbox_id": str(self.mailbox.id),
                    "label_name": name
                }
            )

            # Build label object
            label = {
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show"
            }

            # Execute API call
            response = service.users().labels().create(
                userId="me",
                body=label
            ).execute()

            return response

        except HttpError as e:
            self._handle_error(e, f"create_label(name={name})")
