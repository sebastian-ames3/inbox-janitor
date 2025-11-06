"""
Gmail Push Notifications (Watch) management.

Handles:
- Registering Gmail watch requests (push notifications via Pub/Sub)
- Renewing watch registrations before expiration
- Tracking watch status in database

CRITICAL: Gmail watches expire after 7 days and must be renewed.

References:
- https://developers.google.com/gmail/api/guides/push
"""

import logging
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from googleapiclient.errors import HttpError

from app.core.database import AsyncSessionLocal
from app.core.config import settings
from app.models.mailbox import Mailbox
from app.modules.auth.gmail_oauth import get_gmail_service

logger = logging.getLogger(__name__)


async def register_gmail_watch(mailbox_id: UUID) -> dict:
    """
    Register Gmail Push Notification watch for a mailbox.

    This enables real-time email notifications via Google Cloud Pub/Sub.
    Watches expire after 7 days and must be renewed.

    Args:
        mailbox_id: UUID of mailbox to watch

    Returns:
        Dict with:
            - history_id: Gmail history ID (for delta sync)
            - expiration: Unix timestamp when watch expires

    Raises:
        ValueError: If mailbox not found or PUBSUB_TOPIC not configured
        HttpError: If Gmail API call fails

    Usage:
        watch_data = await register_gmail_watch(mailbox_id)
        logger.info(f"Watch registered, expires at {watch_data['expiration']}")
    """
    # Verify Pub/Sub topic is configured
    if not settings.GOOGLE_PUBSUB_TOPIC:
        raise ValueError(
            "GOOGLE_PUBSUB_TOPIC not configured. "
            "Please set environment variable before registering watches."
        )

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
            logger.warning(f"Skipping watch registration for inactive mailbox {mailbox_id}")
            return {"history_id": mailbox.last_history_id, "expiration": None}

        try:
            # Get authenticated Gmail service
            service = await get_gmail_service(mailbox_id)

            # Register watch with Gmail API
            watch_request = {
                "topicName": settings.GOOGLE_PUBSUB_TOPIC,
                "labelIds": ["INBOX"],  # Only watch inbox
                "labelFilterAction": "include",  # Only emails with these labels
            }

            watch_response = service.users().watch(
                userId="me",
                body=watch_request
            ).execute()

            # Extract response data
            history_id = watch_response.get("historyId")
            expiration_ms = int(watch_response.get("expiration"))  # Unix timestamp in milliseconds
            expiration_dt = datetime.utcfromtimestamp(expiration_ms / 1000)

            # Update mailbox with watch information
            mailbox.watch_expiration = expiration_dt
            mailbox.last_history_id = history_id
            await session.commit()

            logger.info(
                f"Gmail watch registered for mailbox {mailbox_id} "
                f"(expires: {expiration_dt.isoformat()})"
            )

            return {
                "history_id": history_id,
                "expiration": expiration_dt,
            }

        except HttpError as e:
            logger.error(
                f"Gmail API error registering watch for mailbox {mailbox_id}: "
                f"{e.status_code} {e.reason}"
            )

            # Log to Sentry with context
            import sentry_sdk
            sentry_sdk.capture_exception(e, extra={
                "mailbox_id": str(mailbox_id),
                "email": mailbox.email_address,
                "error": "Gmail watch registration failed",
            })

            raise


async def renew_gmail_watch(mailbox_id: UUID) -> bool:
    """
    Renew Gmail watch if it expires soon.

    Checks if watch expires within next 24 hours and renews if needed.
    This should be called periodically (every 6 days) to prevent expiration.

    Args:
        mailbox_id: UUID of mailbox

    Returns:
        True if watch was renewed, False if renewal not needed or failed

    Usage:
        renewed = await renew_gmail_watch(mailbox_id)
        if renewed:
            logger.info(f"Watch renewed for {mailbox_id}")
    """
    async with AsyncSessionLocal() as session:
        # Fetch mailbox
        result = await session.execute(
            select(Mailbox).where(Mailbox.id == mailbox_id)
        )
        mailbox = result.scalar_one_or_none()

        if not mailbox:
            logger.warning(f"Mailbox {mailbox_id} not found, skipping renewal")
            return False

        if not mailbox.is_active:
            logger.info(f"Mailbox {mailbox_id} is inactive, skipping renewal")
            return False

        # Check if watch expires soon (within 24 hours)
        now = datetime.utcnow()
        expires_soon = (
            mailbox.watch_expiration and
            mailbox.watch_expiration < now + timedelta(hours=24)
        )

        if not expires_soon:
            logger.debug(
                f"Watch for mailbox {mailbox_id} does not need renewal "
                f"(expires: {mailbox.watch_expiration})"
            )
            return False

        try:
            # Renew watch (same as registering)
            watch_data = await register_gmail_watch(mailbox_id)

            logger.info(
                f"Watch renewed for mailbox {mailbox_id}, "
                f"new expiration: {watch_data['expiration']}"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to renew watch for mailbox {mailbox_id}: {e}")

            # Don't raise - we'll retry on next scheduled run
            return False


async def get_watch_status(mailbox_id: UUID) -> Optional[dict]:
    """
    Get current watch status for a mailbox.

    Args:
        mailbox_id: UUID of mailbox

    Returns:
        Dict with watch status or None if mailbox not found:
            - is_active: Whether watch is currently active
            - expires_at: When watch expires
            - expires_soon: Whether watch expires within 24 hours
            - needs_renewal: Whether watch should be renewed now

    Usage:
        status = await get_watch_status(mailbox_id)
        if status and status['needs_renewal']:
            await renew_gmail_watch(mailbox_id)
    """
    async with AsyncSessionLocal() as session:
        # Fetch mailbox
        result = await session.execute(
            select(Mailbox).where(Mailbox.id == mailbox_id)
        )
        mailbox = result.scalar_one_or_none()

        if not mailbox:
            return None

        if not mailbox.watch_expiration:
            return {
                "is_active": False,
                "expires_at": None,
                "expires_soon": False,
                "needs_renewal": mailbox.is_active,  # Active mailboxes need initial setup
            }

        now = datetime.utcnow()
        is_expired = mailbox.watch_expiration < now
        expires_soon = mailbox.watch_expiration < now + timedelta(hours=24)

        return {
            "is_active": not is_expired and mailbox.is_active,
            "expires_at": mailbox.watch_expiration,
            "expires_soon": expires_soon,
            "needs_renewal": expires_soon and mailbox.is_active,
        }


async def stop_gmail_watch(mailbox_id: UUID) -> bool:
    """
    Stop Gmail watch for a mailbox (when user disconnects).

    Note: Gmail API doesn't have a direct "stop watch" endpoint.
    Instead, we just stop renewing it and let it expire naturally.

    Args:
        mailbox_id: UUID of mailbox

    Returns:
        True if mailbox updated successfully

    Usage:
        await stop_gmail_watch(mailbox_id)
        # Watch will expire naturally after 7 days
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Mailbox).where(Mailbox.id == mailbox_id)
        )
        mailbox = result.scalar_one_or_none()

        if not mailbox:
            return False

        # Clear watch expiration (signals not to renew)
        mailbox.watch_expiration = None
        await session.commit()

        logger.info(f"Stopped watch renewal for mailbox {mailbox_id}")

        return True
