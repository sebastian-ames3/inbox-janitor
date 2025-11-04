"""
Authentication routes - OAuth callbacks and token management.

Endpoints:
- GET /auth/connect - Initiate OAuth flow
- GET /auth/google/callback - Handle OAuth callback
- POST /auth/disconnect - Disconnect mailbox
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.config import settings
from app.core.security import encrypt_token
from app.models import User, Mailbox, UserSettings
from app.modules.auth.gmail_oauth import gmail_oauth

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.get("/connect")
async def connect_gmail(
    user_email: str = Query(..., description="User's email address"),
    db: AsyncSession = Depends(get_db),
):
    """
    Initiate Gmail OAuth flow.

    This endpoint:
    1. Creates/retrieves user record
    2. Generates OAuth authorization URL
    3. Redirects user to Google consent screen

    Query Params:
        user_email: Email address of the user connecting their Gmail

    Returns:
        Redirect to Google OAuth consent screen
    """
    # Get or create user
    result = await db.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(email=user_email)
        db.add(user)
        await db.flush()

        # Create default settings
        settings = UserSettings(user_id=user.id)
        db.add(settings)
        await db.commit()

    # Generate OAuth URL
    auth_url, state = await gmail_oauth.get_authorization_url(str(user.id))

    # Redirect to Google OAuth
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_oauth_callback(
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="CSRF state token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Handle OAuth callback from Google.

    This endpoint:
    1. Verifies state token (CSRF protection)
    2. Exchanges authorization code for tokens
    3. Encrypts and stores tokens in database
    4. Sets up Gmail watch (Pub/Sub)
    5. Redirects to success page

    Query Params:
        code: Authorization code from Google
        state: State token for CSRF verification

    Returns:
        Redirect to success page or error page
    """
    # Verify state token
    user_id = await gmail_oauth.verify_state(state)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired state token")

    try:
        # Exchange code for tokens
        tokens = gmail_oauth.exchange_code_for_tokens(code)

        # Get user
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if mailbox already exists
        result = await db.execute(
            select(Mailbox).where(
                Mailbox.user_id == user.id,
                Mailbox.email_address == tokens["email"],
                Mailbox.provider == "gmail",
            )
        )
        existing_mailbox = result.scalar_one_or_none()

        if existing_mailbox:
            # Update existing mailbox
            existing_mailbox.encrypted_access_token = encrypt_token(tokens["access_token"])
            existing_mailbox.encrypted_refresh_token = encrypt_token(tokens["refresh_token"])
            existing_mailbox.token_expires_at = datetime.utcnow() + timedelta(
                seconds=tokens["expires_in"]
            )
            existing_mailbox.is_active = True
            mailbox = existing_mailbox
        else:
            # Create new mailbox
            mailbox = Mailbox(
                user_id=user.id,
                provider="gmail",
                email_address=tokens["email"],
                encrypted_access_token=encrypt_token(tokens["access_token"]),
                encrypted_refresh_token=encrypt_token(tokens["refresh_token"]),
                token_expires_at=datetime.utcnow() + timedelta(
                    seconds=tokens["expires_in"]
                ),
                is_active=True,
            )
            db.add(mailbox)

        await db.commit()

        # TODO: Set up Gmail watch (Week 1 - later task)
        # from app.modules.ingest.gmail_watch import setup_gmail_watch
        # await setup_gmail_watch(mailbox.id)

        # Redirect to success page
        return RedirectResponse(
            url=f"{settings.APP_URL}/success?email={tokens['email']}"
        )

    except Exception as e:
        # Log error (but NOT the tokens!)
        print(f"OAuth callback error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to complete OAuth flow. Please try again.",
        )


@router.post("/disconnect/{mailbox_id}")
async def disconnect_mailbox(
    mailbox_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Disconnect a mailbox (revoke OAuth tokens).

    This endpoint:
    1. Revokes OAuth tokens at Google
    2. Marks mailbox as inactive
    3. Keeps historical data for audit purposes

    Path Params:
        mailbox_id: UUID of mailbox to disconnect

    Returns:
        Success message

    NOTE: We don't delete the mailbox to preserve audit logs.
    """
    # Get mailbox
    result = await db.execute(
        select(Mailbox).where(Mailbox.id == mailbox_id)
    )
    mailbox = result.scalar_one_or_none()

    if not mailbox:
        raise HTTPException(status_code=404, detail="Mailbox not found")

    if not mailbox.is_active:
        raise HTTPException(status_code=400, detail="Mailbox already disconnected")

    # Revoke tokens at Google
    await gmail_oauth.revoke_token(mailbox.encrypted_access_token)

    # Mark as inactive (don't delete - keep audit log)
    mailbox.is_active = False
    await db.commit()

    return {
        "status": "disconnected",
        "message": f"Successfully disconnected {mailbox.email_address}",
    }


@router.get("/status/{user_id}")
async def get_auth_status(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get authentication status for a user.

    Returns list of connected mailboxes with connection status.

    Path Params:
        user_id: UUID of user

    Returns:
        List of connected mailboxes
    """
    # Get user's mailboxes
    result = await db.execute(
        select(Mailbox).where(
            Mailbox.user_id == user_id,
            Mailbox.is_active == True,
        )
    )
    mailboxes = result.scalars().all()

    return {
        "user_id": user_id,
        "connected_mailboxes": [
            {
                "id": str(mailbox.id),
                "provider": mailbox.provider,
                "email": mailbox.email_address,
                "connected_at": mailbox.created_at.isoformat(),
                "token_expires_at": (
                    mailbox.token_expires_at.isoformat()
                    if mailbox.token_expires_at
                    else None
                ),
            }
            for mailbox in mailboxes
        ],
    }


@router.get("/status/by-email/{email}")
async def get_auth_status_by_email(
    email: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get authentication status for a user by email.

    Returns user info and connected mailboxes.

    Path Params:
        email: User's email address

    Returns:
        User info and list of connected mailboxes
    """
    # Get user by email
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get user's mailboxes
    result = await db.execute(
        select(Mailbox).where(
            Mailbox.user_id == user.id,
            Mailbox.is_active == True,
        )
    )
    mailboxes = result.scalars().all()

    return {
        "user_id": str(user.id),
        "email": user.email,
        "created_at": user.created_at.isoformat(),
        "connected_mailboxes": [
            {
                "id": str(mailbox.id),
                "provider": mailbox.provider,
                "email": mailbox.email_address,
                "connected_at": mailbox.created_at.isoformat(),
                "token_expires_at": (
                    mailbox.token_expires_at.isoformat()
                    if mailbox.token_expires_at
                    else None
                ),
            }
            for mailbox in mailboxes
        ],
    }
