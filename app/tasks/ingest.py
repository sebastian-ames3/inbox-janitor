"""
Celery tasks for email ingestion and Gmail watch management.

Tasks:
- renew_all_gmail_watches: Periodic task to renew Gmail watches (every 6 days)
- fallback_poll_gmail: Periodic task to catch missed webhooks (every 10 min)
- process_gmail_history: Process new emails from Gmail history (webhook-triggered)
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select

from app.core.celery_app import celery_app
from app.core.database import get_async_session
from app.models.mailbox import Mailbox
from app.modules.ingest.gmail_watch import renew_gmail_watch

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.ingest.renew_all_gmail_watches")
def renew_all_gmail_watches():
    """
    Renew Gmail watches for all active mailboxes.

    This task runs every 6 days (via Celery Beat schedule).
    Gmail watches expire after 7 days, so renewing at 6 days ensures no gaps.

    Filters mailboxes:
    - is_active = True (connected accounts)
    - last_used_at within 30 days (recently active users)

    Returns:
        Dict with renewal stats

    Usage:
        # Called automatically by Celery Beat
        # Or manually: renew_all_gmail_watches.delay()
    """
    import asyncio

    async def _renew_all():
        renewed_count = 0
        skipped_count = 0
        failed_count = 0

        async with get_async_session() as session:
            # Query active mailboxes used in last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            result = await session.execute(
                select(Mailbox).where(
                    Mailbox.is_active == True,
                    Mailbox.last_used_at >= thirty_days_ago
                )
            )
            mailboxes = result.scalars().all()

            logger.info(f"Found {len(mailboxes)} active mailboxes to check for renewal")

            for mailbox in mailboxes:
                try:
                    # Check if watch needs renewal and renew if needed
                    renewed = await renew_gmail_watch(mailbox.id)

                    if renewed:
                        renewed_count += 1
                    else:
                        skipped_count += 1

                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to renew watch for mailbox {mailbox.id}: {e}")

                    # Log to Sentry
                    import sentry_sdk
                    sentry_sdk.capture_exception(e, extra={
                        "mailbox_id": str(mailbox.id),
                        "email": mailbox.email_address,
                        "task": "renew_all_gmail_watches",
                    })

        logger.info(
            f"Watch renewal complete: "
            f"{renewed_count} renewed, {skipped_count} skipped, {failed_count} failed"
        )

        return {
            "renewed": renewed_count,
            "skipped": skipped_count,
            "failed": failed_count,
            "total_checked": renewed_count + skipped_count + failed_count,
        }

    # Run async function
    return asyncio.run(_renew_all())


@celery_app.task(name="app.tasks.ingest.fallback_poll_gmail")
def fallback_poll_gmail():
    """
    Fallback polling to catch missed webhooks.

    This task runs every 10 minutes (via Celery Beat schedule).
    If no webhook received for a mailbox in 15+ minutes, manually fetch history.

    This ensures we don't miss emails even if:
    - Pub/Sub is down
    - Webhooks fail to deliver
    - Watch registration lapses

    Returns:
        Dict with polling stats

    Usage:
        # Called automatically by Celery Beat
        # Or manually: fallback_poll_gmail.delay()
    """
    import asyncio

    async def _poll_all():
        polled_count = 0
        emails_found = 0

        async with get_async_session() as session:
            # Query mailboxes with no webhook in 15+ minutes
            fifteen_min_ago = datetime.utcnow() - timedelta(minutes=15)

            result = await session.execute(
                select(Mailbox).where(
                    Mailbox.is_active == True,
                    Mailbox.last_webhook_received_at < fifteen_min_ago
                )
            )
            mailboxes = result.scalars().all()

            if not mailboxes:
                logger.debug("No mailboxes need fallback polling")
                return {"polled": 0, "emails_found": 0}

            logger.info(f"Fallback polling {len(mailboxes)} mailboxes (no recent webhooks)")

            for mailbox in mailboxes:
                try:
                    # Fetch history since last known history ID
                    from app.modules.auth.gmail_oauth import get_gmail_service

                    service = await get_gmail_service(mailbox.id)

                    # Get history list
                    history_response = service.users().history().list(
                        userId="me",
                        startHistoryId=mailbox.last_history_id
                    ).execute()

                    # Check if there are new messages
                    history = history_response.get("history", [])
                    new_message_ids = []

                    for history_item in history:
                        messages_added = history_item.get("messagesAdded", [])
                        for msg in messages_added:
                            # Only process INBOX messages
                            if "INBOX" in msg.get("message", {}).get("labelIds", []):
                                new_message_ids.append(msg["message"]["id"])

                    if new_message_ids:
                        logger.info(
                            f"Fallback polling found {len(new_message_ids)} new emails "
                            f"for mailbox {mailbox.id}"
                        )
                        emails_found += len(new_message_ids)

                        # Enqueue processing tasks (will be implemented in Task 4)
                        # TODO: Enqueue process_gmail_history task with message IDs

                    polled_count += 1

                    # Update last_webhook_received_at to prevent repeated polling
                    mailbox.last_webhook_received_at = datetime.utcnow()
                    await session.commit()

                except Exception as e:
                    logger.error(f"Fallback polling failed for mailbox {mailbox.id}: {e}")

                    # Log to Sentry
                    import sentry_sdk
                    sentry_sdk.capture_exception(e, extra={
                        "mailbox_id": str(mailbox.id),
                        "email": mailbox.email_address,
                        "task": "fallback_poll_gmail",
                    })

        logger.info(f"Fallback polling complete: {polled_count} mailboxes, {emails_found} emails found")

        return {
            "polled": polled_count,
            "emails_found": emails_found,
        }

    # Run async function
    return asyncio.run(_poll_all())


@celery_app.task(
    name="app.tasks.ingest.process_gmail_history",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def process_gmail_history(self, mailbox_id: str, history_id: str):
    """
    Process new emails from Gmail history (webhook-triggered).

    This task is enqueued by the webhook endpoint when Gmail sends
    a push notification about new emails.

    Args:
        mailbox_id: UUID of mailbox (as string)
        history_id: Gmail history ID to start from

    Raises:
        Exception: Retries up to 3 times with exponential backoff

    Usage:
        # Enqueued by webhook endpoint
        process_gmail_history.delay(mailbox_id, history_id)
    """
    logger.info(f"Processing Gmail history for mailbox {mailbox_id}, history_id={history_id}")

    # TODO: Implement in Task 4.0
    # This task will:
    # 1. Fetch new emails using history.list()
    # 2. For each email, extract metadata
    # 3. Enqueue classification tasks
    # 4. Update mailbox.last_history_id

    logger.warning("process_gmail_history not yet implemented (Task 4.0)")

    return {
        "status": "pending_implementation",
        "mailbox_id": mailbox_id,
        "history_id": history_id,
    }
