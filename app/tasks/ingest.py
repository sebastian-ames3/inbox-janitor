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

    Flow:
    1. Fetch new message IDs from history.list()
    2. For each message, extract metadata
    3. Enqueue classification tasks (Task 5.0)
    4. Update mailbox.last_history_id

    Args:
        mailbox_id: UUID of mailbox (as string)
        history_id: Gmail history ID to start from

    Returns:
        Dict with processing stats

    Raises:
        Exception: Retries up to 3 times with exponential backoff

    Usage:
        # Enqueued by webhook endpoint
        process_gmail_history.delay(mailbox_id, history_id)
    """
    import asyncio

    logger.info(f"Processing Gmail history for mailbox {mailbox_id}, history_id={history_id}")

    async def _process():
        from app.modules.ingest.metadata_extractor import (
            fetch_new_emails_from_history,
            extract_email_metadata
        )
        from app.models.email_metadata import EmailMetadataExtractError
        from sqlalchemy import select
        from app.core.database import get_async_session
        from app.models.mailbox import Mailbox

        messages_processed = 0
        messages_failed = 0
        new_history_id = history_id

        try:
            # Fetch new message IDs from history
            message_ids = await fetch_new_emails_from_history(mailbox_id, history_id)

            logger.info(f"Found {len(message_ids)} new messages for mailbox {mailbox_id}")

            if not message_ids:
                # No new messages - still update history_id if newer
                async with get_async_session() as session:
                    result = await session.execute(
                        select(Mailbox).where(Mailbox.id == mailbox_id)
                    )
                    mailbox = result.scalar_one_or_none()

                    if mailbox:
                        # Update to current history_id
                        mailbox.last_history_id = history_id
                        await session.commit()

                return {
                    "status": "success",
                    "messages_processed": 0,
                    "messages_failed": 0,
                    "mailbox_id": mailbox_id
                }

            # Process each message
            for message_id in message_ids:
                try:
                    # Extract metadata
                    metadata = await extract_email_metadata(mailbox_id, message_id)

                    logger.info(
                        f"Extracted metadata: {message_id} from {metadata.from_address}",
                        extra={
                            "message_id": message_id,
                            "from_address": metadata.from_address,
                            "subject": metadata.subject
                        }
                    )

                    # Store metadata in database (for analysis/learning)
                    from app.models.email_metadata_db import EmailMetadataDB
                    from uuid import UUID

                    # Check if already exists (upsert logic)
                    existing = await session.execute(
                        select(EmailMetadataDB).where(
                            EmailMetadataDB.mailbox_id == UUID(mailbox_id),
                            EmailMetadataDB.message_id == message_id
                        )
                    )
                    existing_metadata = existing.scalar_one_or_none()

                    if not existing_metadata:
                        # Insert new metadata
                        metadata_db = EmailMetadataDB(
                            mailbox_id=UUID(mailbox_id),
                            message_id=metadata.message_id,
                            thread_id=metadata.thread_id,
                            from_address=metadata.from_address,
                            from_name=metadata.from_name,
                            from_domain=metadata.from_domain,
                            subject=metadata.subject,
                            snippet=metadata.snippet,
                            gmail_labels=metadata.gmail_labels,
                            gmail_category=metadata.gmail_category,
                            headers=metadata.headers,
                            received_at=metadata.received_at
                        )
                        session.add(metadata_db)
                        await session.commit()

                        logger.debug(f"Stored metadata for {message_id} in email_metadata table")

                    # Enqueue classification task
                    from app.tasks.classify import classify_email_tier1 as classify_task
                    classify_task.delay(mailbox_id, metadata.dict())

                    messages_processed += 1

                except EmailMetadataExtractError as e:
                    # Extraction failed for this message - log and continue
                    messages_failed += 1
                    logger.warning(f"Failed to extract metadata for {message_id}: {e}")

                except Exception as e:
                    # Unexpected error - log and continue
                    messages_failed += 1
                    logger.error(f"Unexpected error processing {message_id}: {e}")

                    # Log to Sentry
                    import sentry_sdk
                    sentry_sdk.capture_exception(e, extra={
                        "mailbox_id": mailbox_id,
                        "message_id": message_id,
                        "error": "Message processing failed"
                    })

            # Update mailbox with latest history ID
            async with get_async_session() as session:
                result = await session.execute(
                    select(Mailbox).where(Mailbox.id == mailbox_id)
                )
                mailbox = result.scalar_one_or_none()

                if mailbox:
                    # Update last_history_id to the one from the webhook
                    # (Gmail provides the latest history ID in notifications)
                    mailbox.last_history_id = history_id
                    await session.commit()

                    logger.info(f"Updated mailbox {mailbox_id} history_id to {history_id}")

            logger.info(
                f"Completed processing for mailbox {mailbox_id}: "
                f"{messages_processed} processed, {messages_failed} failed"
            )

            return {
                "status": "success",
                "messages_processed": messages_processed,
                "messages_failed": messages_failed,
                "mailbox_id": mailbox_id,
                "history_id": history_id
            }

        except Exception as e:
            logger.error(f"Failed to process history for mailbox {mailbox_id}: {e}")

            # Log to Sentry
            import sentry_sdk
            sentry_sdk.capture_exception(e, extra={
                "mailbox_id": mailbox_id,
                "history_id": history_id,
                "error": "History processing failed"
            })

            # Retry with exponential backoff
            retry_delay = 60 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=retry_delay)

    # Run async function
    return asyncio.run(_process())
