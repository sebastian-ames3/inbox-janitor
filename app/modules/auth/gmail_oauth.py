"""
Gmail OAuth flow using Authlib and Google API.

Handles:
- OAuth authorization URL generation
- Token exchange (authorization code → access/refresh tokens)
- Token refresh (when access token expires)
- Token encryption/decryption for secure storage

CRITICAL SECURITY:
- NEVER log tokens (access_token, refresh_token)
- ALWAYS encrypt tokens before database storage
- Use state parameter for CSRF protection
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from authlib.integrations.requests_client import OAuth2Session
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import redis.asyncio as redis
import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from sqlalchemy.exc import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError
import logging

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token, generate_state_token

logger = logging.getLogger(__name__)


# Gmail API scopes
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",  # Read emails
    "https://www.googleapis.com/auth/gmail.modify",  # Archive/trash/label emails
    "https://www.googleapis.com/auth/gmail.labels",  # Manage labels
    "https://www.googleapis.com/auth/userinfo.email",  # Get user email
]

# Google OAuth endpoints
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


# Custom exceptions for token refresh (PRD-0007)
class OAuthPermanentError(Exception):
    """
    Raised for permanent OAuth failures where user must reconnect.

    Examples:
    - Invalid refresh token (invalid_grant)
    - Token revoked by user
    - OAuth app suspended by Google
    - User changed Google password

    These errors should NOT be retried - user must reconnect their Gmail account.
    """
    def __init__(self, message: str, error_code: str = None):
        super().__init__(message)
        self.error_code = error_code


class OAuthTransientError(Exception):
    """
    Raised for transient OAuth failures where retry may succeed.

    Examples:
    - Network timeout
    - Connection refused
    - Database connection lost
    - Redis connection pool exhausted
    - Gmail API rate limit (429)
    - Gmail API server error (500, 502, 503)

    These errors SHOULD be retried with exponential backoff.
    """
    pass


# Define transient failure exceptions for retry logic
TRANSIENT_FAILURES = (
    requests.Timeout,
    requests.ConnectionError,
    RedisConnectionError,
    OperationalError,  # Database connection lost
    OAuthTransientError,
)


class GmailOAuthManager:
    """
    Manages Gmail OAuth flow and token operations.

    Usage:
        oauth_manager = GmailOAuthManager()
        auth_url, state = await oauth_manager.get_authorization_url(user_id)
        # User visits auth_url, gets redirected back with code
        tokens = await oauth_manager.exchange_code_for_tokens(code, state)
    """

    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI
        self._redis = None

    async def _get_redis(self) -> redis.Redis:
        """Get Redis client for state storage."""
        if not self._redis:
            self._redis = redis.from_url(settings.REDIS_URL)
        return self._redis

    async def get_authorization_url(self, user_id: str) -> Tuple[str, str]:
        """
        Generate OAuth authorization URL with CSRF protection.

        Args:
            user_id: User UUID (to associate state with user)

        Returns:
            Tuple of (authorization_url, state_token)

        Usage:
            auth_url, state = await oauth_manager.get_authorization_url(user.id)
            return RedirectResponse(url=auth_url)
        """
        # Generate secure state token for CSRF protection
        state = generate_state_token()

        # Store state in Redis with 10-minute expiry
        redis_client = await self._get_redis()
        await redis_client.setex(
            f"oauth_state:{state}",
            600,  # 10 minutes
            str(user_id) if user_id is not None else ""
        )

        # Create OAuth2 session
        session = OAuth2Session(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=GMAIL_SCOPES,
        )

        # Generate authorization URL
        auth_url, _ = session.create_authorization_url(
            GOOGLE_AUTHORIZE_URL,
            state=state,
            access_type="offline",  # Request refresh token
            prompt="consent",  # Force consent screen (ensures refresh token)
        )

        return auth_url, state

    async def verify_state(self, state: str) -> Optional[str]:
        """
        Verify OAuth state token and return associated user_id.

        Args:
            state: State token from OAuth callback

        Returns:
            User ID if state is valid, None otherwise

        CRITICAL: Always call this before exchanging code for tokens!
        """
        redis_client = await self._get_redis()
        user_id = await redis_client.get(f"oauth_state:{state}")

        if user_id is not None:
            # Delete state token (one-time use)
            await redis_client.delete(f"oauth_state:{state}")
            # Return decoded value (may be empty string if no user_id was stored)
            return user_id.decode()

        return None

    def exchange_code_for_tokens(self, code: str) -> dict:
        """
        Exchange authorization code for access/refresh tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            Dict with:
                - access_token: OAuth access token
                - refresh_token: OAuth refresh token
                - expires_in: Token expiration in seconds
                - email: User's Gmail address

        WARNING: Tokens are returned in plaintext. Encrypt before storing!

        Usage:
            tokens = oauth_manager.exchange_code_for_tokens(code)
            encrypted_access = encrypt_token(tokens['access_token'])
            encrypted_refresh = encrypt_token(tokens['refresh_token'])
        """
        session = OAuth2Session(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
        )

        # Exchange code for tokens
        token_response = session.fetch_token(
            GOOGLE_TOKEN_URL,
            code=code,
        )

        # Get user's email address
        credentials = Credentials(token=token_response["access_token"])
        gmail_service = build("gmail", "v1", credentials=credentials)
        profile = gmail_service.users().getProfile(userId="me").execute()
        email_address = profile["emailAddress"]

        return {
            "access_token": token_response["access_token"],
            "refresh_token": token_response.get("refresh_token"),
            "expires_in": token_response.get("expires_in", 3600),
            "email": email_address,
        }

    def refresh_access_token(self, encrypted_refresh_token: str) -> Tuple[str, datetime]:
        """
        Refresh expired access token using refresh token.

        Args:
            encrypted_refresh_token: Encrypted refresh token from database

        Returns:
            Tuple of (new_encrypted_access_token, expiration_datetime)

        Usage:
            new_token, expires_at = oauth_manager.refresh_access_token(
                mailbox.encrypted_refresh_token
            )
            mailbox.encrypted_access_token = new_token
            mailbox.token_expires_at = expires_at
        """
        # Decrypt refresh token
        refresh_token = decrypt_token(encrypted_refresh_token)

        # Create session with refresh token
        session = OAuth2Session(
            client_id=self.client_id,
            client_secret=self.client_secret,
        )

        # Refresh token
        token_response = session.refresh_token(
            GOOGLE_TOKEN_URL,
            refresh_token=refresh_token,
        )

        # Extract new access token
        new_access_token = token_response["access_token"]
        expires_in = token_response.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Encrypt new access token
        encrypted_access = encrypt_token(new_access_token)

        return encrypted_access, expires_at

    def build_gmail_service(self, encrypted_access_token: str):
        """
        Build authenticated Gmail API service.

        Args:
            encrypted_access_token: Encrypted access token from database

        Returns:
            Authenticated Gmail API service object

        Usage:
            service = oauth_manager.build_gmail_service(mailbox.encrypted_access_token)
            messages = service.users().messages().list(userId='me').execute()

        WARNING: Never log the decrypted token!
        """
        # Decrypt access token
        access_token = decrypt_token(encrypted_access_token)

        # Create credentials
        credentials = Credentials(token=access_token)

        # Build and return service
        return build("gmail", "v1", credentials=credentials)

    async def revoke_token(self, encrypted_access_token: str) -> bool:
        """
        Revoke OAuth token (e.g., when user disconnects account).

        Args:
            encrypted_access_token: Encrypted access token from database

        Returns:
            True if revocation successful, False otherwise

        Usage:
            await oauth_manager.revoke_token(mailbox.encrypted_access_token)
            mailbox.is_active = False
        """
        import httpx

        try:
            access_token = decrypt_token(encrypted_access_token)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": access_token},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                return response.status_code == 200

        except Exception:
            return False


# Global OAuth manager instance
gmail_oauth = GmailOAuthManager()


# Helper functions for Gmail API operations

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),  # 2s, 4s, 8s
    retry=retry_if_exception_type(TRANSIENT_FAILURES),
    reraise=True
)
async def refresh_access_token_with_retry(
    mailbox_id: str,
    refresh_token_encrypted: str,
) -> Tuple[str, datetime]:
    """
    Refresh OAuth access token with retry logic for transient failures.

    Retries 3 times with exponential backoff (2s, 4s, 8s) for:
    - Network timeouts
    - Connection errors
    - Database connection lost
    - Redis connection errors

    Immediate failure (no retry) for:
    - Invalid refresh token (user must reconnect)
    - OAuth app suspended (admin must fix)
    - Token revoked by user (user must reconnect)

    Args:
        mailbox_id: Mailbox UUID (for logging)
        refresh_token_encrypted: Encrypted refresh token from database

    Returns:
        Tuple of (encrypted_access_token, expires_at)

    Raises:
        OAuthPermanentError: User must reconnect (don't retry)
        OAuthTransientError: After 3 retries failed
    """
    try:
        # Decrypt refresh token
        refresh_token_decrypted = decrypt_token(refresh_token_encrypted)

        # Exchange refresh token for new access token
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "refresh_token": refresh_token_decrypted,
                "grant_type": "refresh_token"
            },
            timeout=10  # 10 second timeout
        )

        # Check for permanent failures (don't retry)
        if response.status_code == 400:
            error = response.json().get("error", "")

            if error == "invalid_grant":
                # Refresh token invalid/expired - user must reconnect
                raise OAuthPermanentError(
                    f"Invalid refresh token for mailbox {mailbox_id}. "
                    f"User must reconnect Gmail account.",
                    error_code="invalid_grant"
                )

        if response.status_code == 403:
            # OAuth app suspended or token revoked
            error_description = response.json().get("error_description", "")

            if "revoked" in error_description.lower():
                raise OAuthPermanentError(
                    f"OAuth token revoked by user for mailbox {mailbox_id}",
                    error_code="token_revoked"
                )

            raise OAuthPermanentError(
                f"OAuth access forbidden for mailbox {mailbox_id}: {error_description}",
                error_code="forbidden"
            )

        # Raise for other HTTP errors (will be caught by retry decorator)
        response.raise_for_status()

        # Parse response
        token_data = response.json()

        # Encrypt new access token
        new_access_token_encrypted = encrypt_token(token_data["access_token"])
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        return new_access_token_encrypted, expires_at

    except requests.Timeout as e:
        # Network timeout - retry
        logger.warning(
            f"Token refresh timeout for mailbox {mailbox_id} - will retry",
            extra={"mailbox_id": mailbox_id, "error": str(e)}
        )
        raise  # Let tenacity retry

    except requests.ConnectionError as e:
        # Connection error - retry
        logger.warning(
            f"Token refresh connection error for mailbox {mailbox_id} - will retry",
            extra={"mailbox_id": mailbox_id, "error": str(e)}
        )
        raise  # Let tenacity retry

    except OAuthPermanentError:
        # Permanent error - don't retry, raise immediately
        raise

    except Exception as e:
        # Unexpected error - log and raise as transient (will retry)
        logger.error(
            f"Unexpected error during token refresh for mailbox {mailbox_id}: {e}",
            extra={"mailbox_id": mailbox_id, "error_type": type(e).__name__}
        )
        raise OAuthTransientError(f"Unexpected error: {e}")


async def handle_token_refresh_failure(
    mailbox_id: str,
    error: Exception,
    attempt: int,
    session,
):
    """
    Handle token refresh failure with appropriate action.

    Actions depend on failure type and attempt number:
    - Attempt 1: Log warning (no user notification yet)
    - Attempt 2: Send gentle email to user ("Having trouble connecting")
    - Attempt 3: Disable mailbox, send urgent email ("Please reconnect")

    For permanent failures: Disable immediately and notify user.

    Args:
        mailbox_id: Mailbox UUID
        error: Exception that occurred
        attempt: Attempt number (1, 2, or 3)
        session: Async database session
    """
    from app.models.mailbox import Mailbox
    from app.models.user import User

    # Get mailbox
    mailbox = await session.get(Mailbox, mailbox_id)
    if not mailbox:
        logger.error(f"Mailbox {mailbox_id} not found during failure handling")
        return

    # Get user for notifications
    user = await session.get(User, mailbox.user_id)

    if isinstance(error, OAuthPermanentError):
        # Permanent failure - disable immediately, notify user
        mailbox.is_active = False
        mailbox.token_refresh_failed_at = datetime.utcnow()
        mailbox.token_refresh_error = f"{error.error_code}: {str(error)}"
        mailbox.token_refresh_attempt_count = 0  # Reset counter
        await session.commit()

        logger.error(
            f"Permanent OAuth failure for mailbox {mailbox_id}: {error.error_code}",
            extra={"mailbox_id": mailbox_id, "error_code": error.error_code}
        )

        # Send email to user immediately
        from app.modules.digest.email_service import send_token_refresh_permanent_failure_email
        await send_token_refresh_permanent_failure_email(
            user_email=user.email,
            mailbox_email=mailbox.email_address,
            error_reason=error.error_code or "unknown",
            reconnect_url=f"{settings.APP_URL}/auth/gmail"
        )

        return

    # Transient failure - handle based on attempt number
    if attempt == 1:
        # First failure - just log, don't notify yet
        mailbox.token_refresh_attempt_count = 1
        await session.commit()

        logger.warning(
            f"Token refresh attempt 1 failed for mailbox {mailbox_id} - will retry",
            extra={
                "mailbox_id": mailbox_id,
                "error": str(error),
                "error_type": type(error).__name__
            }
        )

    elif attempt == 2:
        # Second failure - send gentle email
        mailbox.token_refresh_attempt_count = 2
        await session.commit()

        logger.warning(
            f"Token refresh attempt 2 failed for mailbox {mailbox_id} - will retry once more",
            extra={"mailbox_id": mailbox_id}
        )

        # Send gentle warning email
        from app.modules.digest.email_service import send_token_refresh_retry_email
        await send_token_refresh_retry_email(
            user_email=user.email,
            mailbox_email=mailbox.email_address,
            attempt=attempt
        )

    elif attempt >= 3:
        # Third failure - disable mailbox, send urgent email
        logger.error(
            f"Token refresh failed after 3 attempts for mailbox {mailbox_id} - disabling",
            extra={"mailbox_id": mailbox_id}
        )

        mailbox.is_active = False
        mailbox.token_refresh_failed_at = datetime.utcnow()
        mailbox.token_refresh_error = f"Failed after 3 attempts: {error}"
        mailbox.token_refresh_attempt_count = 3
        await session.commit()

        # Send urgent reconnection email
        from app.modules.digest.email_service import send_token_refresh_final_failure_email
        await send_token_refresh_final_failure_email(
            user_email=user.email,
            mailbox_email=mailbox.email_address,
            failure_count=attempt,
            reconnect_url=f"{settings.APP_URL}/auth/gmail"
        )


async def get_gmail_service(mailbox_id: str):
    """
    Get authenticated Gmail API service for a mailbox.

    Automatically handles:
    - Fetching mailbox from database
    - Checking if token is expired
    - Refreshing token if needed
    - Building Gmail API service

    Args:
        mailbox_id: UUID of mailbox

    Returns:
        Authenticated Gmail API service object

    Raises:
        ValueError: If mailbox not found or inactive
        Exception: If token refresh fails (mailbox marked inactive)

    Usage:
        service = await get_gmail_service(mailbox_id)
        messages = service.users().messages().list(userId='me').execute()
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.models.mailbox import Mailbox

    # Get database session
    async with AsyncSessionLocal() as session:
        # Fetch mailbox
        result = await session.execute(
            select(Mailbox).where(Mailbox.id == mailbox_id)
        )
        mailbox = result.scalar_one_or_none()

        if not mailbox:
            raise ValueError(f"Mailbox {mailbox_id} not found")

        if not mailbox.is_active:
            raise ValueError(f"Mailbox {mailbox_id} is inactive")

        # Check if token is expired or will expire soon (within 5 minutes)
        from datetime import datetime, timedelta
        if mailbox.token_expires_at and mailbox.token_expires_at < datetime.utcnow() + timedelta(minutes=5):
            attempt = 0
            try:
                # Refresh token with retry logic (PRD-0007)
                attempt = mailbox.token_refresh_attempt_count + 1
                new_access_token, new_expires_at = await refresh_access_token_with_retry(
                    str(mailbox_id),
                    mailbox.encrypted_refresh_token
                )

                # Success! Update mailbox with new token
                mailbox.encrypted_access_token = new_access_token
                mailbox.token_expires_at = new_expires_at
                # Reset failure tracking on success
                mailbox.token_refresh_attempt_count = 0
                mailbox.token_refresh_failed_at = None
                mailbox.token_refresh_error = None
                await session.commit()

                logger.info(
                    f"Token refresh successful for mailbox {mailbox_id}",
                    extra={"mailbox_id": str(mailbox_id)}
                )

            except (OAuthPermanentError, OAuthTransientError) as e:
                # Handle failure with retry logic and user notification
                await handle_token_refresh_failure(str(mailbox_id), e, attempt, session)

                # Log to Sentry
                import sentry_sdk
                sentry_sdk.capture_exception(e, extra={
                    "mailbox_id": str(mailbox_id),
                    "error": "Token refresh failed",
                    "error_type": type(e).__name__,
                    "attempt": attempt
                })

                raise Exception(f"Token refresh failed for mailbox {mailbox_id}. Please re-authenticate.")

        # Build and return Gmail service
        return gmail_oauth.build_gmail_service(mailbox.encrypted_access_token)


