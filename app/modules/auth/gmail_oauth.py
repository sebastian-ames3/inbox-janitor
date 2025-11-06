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

from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token, generate_state_token


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
            self._redis = await redis.from_url(settings.REDIS_URL)
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
    from app.core.database import get_async_session
    from app.models.mailbox import Mailbox

    # Get database session
    async with get_async_session() as session:
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
            try:
                # Refresh token
                new_access_token, new_expires_at = gmail_oauth.refresh_access_token(
                    mailbox.encrypted_refresh_token
                )

                # Update mailbox with new token
                mailbox.encrypted_access_token = new_access_token
                mailbox.token_expires_at = new_expires_at
                await session.commit()

            except Exception as e:
                # Token refresh failed - mark mailbox as inactive
                mailbox.is_active = False
                await session.commit()

                # Log to Sentry
                import sentry_sdk
                sentry_sdk.capture_exception(e, extra={
                    "mailbox_id": str(mailbox_id),
                    "error": "Token refresh failed"
                })

                raise Exception(f"Token refresh failed for mailbox {mailbox_id}. Please re-authenticate.")

        # Build and return Gmail service
        return gmail_oauth.build_gmail_service(mailbox.encrypted_access_token)


async def decrypt_and_refresh_token(mailbox) -> str:
    """
    Decrypt access token and refresh if needed.

    Args:
        mailbox: Mailbox SQLAlchemy object

    Returns:
        Decrypted access token (plaintext)

    Raises:
        Exception: If token refresh fails

    WARNING: This returns plaintext token. Never log it!

    Usage:
        access_token = await decrypt_and_refresh_token(mailbox)
        # Use token for API calls
    """
    from datetime import datetime, timedelta

    # Check if token needs refresh
    if mailbox.token_expires_at and mailbox.token_expires_at < datetime.utcnow() + timedelta(minutes=5):
        # Refresh token
        new_encrypted_access, new_expires_at = gmail_oauth.refresh_access_token(
            mailbox.encrypted_refresh_token
        )

        # Update mailbox (caller should commit)
        mailbox.encrypted_access_token = new_encrypted_access
        mailbox.token_expires_at = new_expires_at

    # Decrypt and return access token
    return decrypt_token(mailbox.encrypted_access_token)
