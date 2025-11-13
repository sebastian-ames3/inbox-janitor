"""
Webhook endpoints for external integrations.

Handles:
- Gmail push notifications (via Google Cloud Pub/Sub)
- Future: Stripe webhooks, other integrations

CRITICAL: Webhooks MUST return 200 OK immediately (within 10ms) to prevent retries.
All processing must be asynchronous (Celery tasks).
"""

import logging
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models.webhook import (
    PubSubRequest,
    GmailWebhookPayload,
    WebhookResponse,
    WebhookError
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/gmail", response_model=WebhookResponse)
async def gmail_webhook(request: PubSubRequest):
    """
    Receive Gmail push notifications from Google Cloud Pub/Sub.

    This endpoint is called by Pub/Sub when Gmail detects new emails.
    It decodes the notification, looks up the mailbox, and enqueues
    processing tasks.

    CRITICAL: Returns 200 OK immediately (within 10ms) to prevent retries.
    All processing happens asynchronously via Celery tasks.

    Args:
        request: Pub/Sub push notification

    Returns:
        WebhookResponse with status and task_id

    Usage:
        # Pub/Sub automatically POSTs to this endpoint
        # For manual testing:
        curl -X POST http://localhost:8000/webhooks/gmail \
          -H "Content-Type: application/json" \
          -d '{"message": {...}, "subscription": "..."}'
    """
    try:
        # Decode Pub/Sub message
        try:
            payload_data = request.message.decode_data()
            payload = GmailWebhookPayload(**payload_data)
        except ValueError as e:
            # Invalid message format - log warning and return 200 OK
            # (prevents Pub/Sub from retrying invalid messages)
            logger.warning(
                f"Invalid Pub/Sub message format: {e}",
                extra={
                    "message_id": request.message.messageId,
                    "subscription": request.subscription
                }
            )
            return WebhookResponse(
                status="ignored",
                message="Invalid message format"
            )

        # Extract data
        email_address = payload.email_address or payload.emailAddress
        history_id = payload.history_id or payload.historyId

        logger.info(
            f"Gmail webhook received: email={email_address}, history_id={history_id}",
            extra={
                "email_address": email_address,
                "history_id": history_id,
                "message_id": request.message.messageId
            }
        )

        # Look up mailbox by email address
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.mailbox import Mailbox
        from datetime import datetime

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Mailbox).where(Mailbox.email_address == email_address)
            )
            mailbox = result.scalar_one_or_none()

            if not mailbox:
                # Mailbox not found - log warning and return 200 OK
                # (prevents retrying for deleted accounts)
                logger.warning(
                    f"Mailbox not found for email: {email_address}",
                    extra={"email_address": email_address}
                )
                return WebhookResponse(
                    status="ignored",
                    message="Mailbox not found"
                )

            if not mailbox.is_active:
                # Mailbox inactive - log and return 200 OK
                logger.info(
                    f"Webhook received for inactive mailbox: {email_address}",
                    extra={
                        "mailbox_id": str(mailbox.id),
                        "email_address": email_address
                    }
                )
                return WebhookResponse(
                    status="ignored",
                    message="Mailbox inactive"
                )

            # Update last webhook received timestamp
            mailbox.last_webhook_received_at = datetime.utcnow()
            await session.commit()

            # Enqueue processing task
            try:
                from app.tasks.ingest import process_gmail_history

                task = process_gmail_history.delay(
                    str(mailbox.id),
                    history_id
                )

                logger.info(
                    f"Enqueued processing task: {task.id}",
                    extra={
                        "task_id": task.id,
                        "mailbox_id": str(mailbox.id),
                        "history_id": history_id
                    }
                )

                return WebhookResponse(
                    status="success",
                    message="Webhook received, processing started",
                    task_id=task.id
                )

            except Exception as e:
                # Task enqueueing failed - log error but still return 200 OK
                # (prevents Pub/Sub retries that would just fail again)
                logger.error(
                    f"Failed to enqueue processing task: {e}",
                    extra={
                        "mailbox_id": str(mailbox.id),
                        "email_address": email_address,
                        "error": str(e)
                    }
                )

                # Log to Sentry
                import sentry_sdk
                sentry_sdk.capture_exception(e, extra={
                    "mailbox_id": str(mailbox.id),
                    "email_address": email_address,
                    "history_id": history_id,
                    "error": "Task enqueueing failed"
                })

                return WebhookResponse(
                    status="error",
                    message="Failed to enqueue task"
                )

    except Exception as e:
        # Unexpected error - log and return 200 OK
        logger.error(
            f"Unexpected webhook error: {e}",
            extra={
                "message_id": request.message.messageId,
                "subscription": request.subscription,
                "error": str(e)
            }
        )

        # Log to Sentry
        import sentry_sdk
        sentry_sdk.capture_exception(e, extra={
            "message_id": request.message.messageId,
            "subscription": request.subscription,
            "error": "Unexpected webhook error"
        })

        # Still return 200 OK to prevent retries
        return WebhookResponse(
            status="error",
            message="Internal error"
        )


@router.post("/gmail/test", response_model=WebhookResponse)
async def gmail_webhook_test(mailbox_id: str, history_id: str = "test-history-id"):
    """
    Manual webhook testing endpoint (development only).

    Allows triggering email processing without Pub/Sub.

    Args:
        mailbox_id: UUID of mailbox to process
        history_id: Gmail history ID (optional, defaults to "test-history-id")

    Returns:
        WebhookResponse with task_id

    Usage:
        curl -X POST "http://localhost:8000/webhooks/gmail/test?mailbox_id=<uuid>&history_id=123"
    """
    from app.core.config import settings

    # Only allow in development
    if settings.is_production:
        raise HTTPException(
            status_code=404,
            detail="Test endpoint not available in production"
        )

    # Enqueue task
    from app.tasks.ingest import process_gmail_history

    task = process_gmail_history.delay(mailbox_id, history_id)

    logger.info(
        f"Test webhook: enqueued task {task.id}",
        extra={
            "mailbox_id": mailbox_id,
            "history_id": history_id,
            "task_id": task.id
        }
    )

    return WebhookResponse(
        status="success",
        message="Test webhook processed",
        task_id=task.id
    )


@router.get("/health")
async def webhook_health():
    """
    Health check for webhook endpoint.

    Returns:
        Simple status response

    Usage:
        curl http://localhost:8000/webhooks/health
    """
    return {"status": "healthy", "service": "webhooks"}


@router.post("/test-worker")
async def test_worker_connection():
    """
    Test Celery worker connectivity (debugging endpoint).

    Enqueues a simple test task to verify:
    - Web service can enqueue tasks to Redis
    - Worker can receive and process tasks
    - End-to-end task processing works

    Returns:
        Task ID and instructions for checking worker logs

    Usage:
        curl -X POST https://inbox-janitor-production-03fc.up.railway.app/webhooks/test-worker
    """
    try:
        from app.tasks import test_celery_connection

        task = test_celery_connection.delay()

        logger.info(
            f"Test task enqueued: {task.id}",
            extra={"task_id": task.id, "task_name": "test_celery_connection"}
        )

        return {
            "success": True,
            "task_id": task.id,
            "message": "Test task enqueued successfully",
            "instructions": "Check worker logs for: 'SUCCESS: Celery works! Test task executed successfully.'",
            "task_name": "test_celery_connection",
        }

    except Exception as e:
        logger.error(f"Failed to enqueue test task: {e}", exc_info=True)

        return {
            "success": False,
            "error": str(e),
            "message": "Failed to enqueue test task. Check Redis connection or worker status.",
        }


@router.post("/run-migration-007")
async def run_migration_007():
    """
    TEMPORARY: Run migration 007 to clear polluted email_actions data.

    This is a ONE-TIME endpoint that will be removed after use.
    Drops the immutability trigger, truncates the table, and recreates the trigger.

    WARNING: This deletes all email_actions data.

    Usage:
        curl -X POST https://inbox-janitor-production-03fc.up.railway.app/webhooks/run-migration-007
    """
    try:
        from sqlalchemy import text
        from app.core.database import async_engine

        logger.info("Starting migration 007: Clear polluted email_actions data")

        async with async_engine.begin() as conn:
            # Drop immutability trigger
            await conn.execute(text("""
                DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;
            """))
            logger.info("Migration 007: Trigger dropped")

            # Clear all data
            await conn.execute(text("TRUNCATE email_actions;"))
            logger.info("Migration 007: Table truncated")

            # Recreate immutability trigger
            await conn.execute(text("""
                CREATE TRIGGER email_actions_immutable
                BEFORE UPDATE OR DELETE ON email_actions
                FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
            """))
            logger.info("Migration 007: Trigger recreated")

            # Verify
            result = await conn.execute(text("SELECT COUNT(*) FROM email_actions;"))
            count = result.scalar()

        logger.info(f"Migration 007 complete. Remaining rows: {count}")

        return {
            "success": True,
            "message": "Migration 007 executed successfully",
            "remaining_rows": count,
            "note": "Database cleared and ready for re-classification"
        }

    except Exception as e:
        logger.error(f"Migration 007 failed: {e}", exc_info=True)

        import sentry_sdk
        sentry_sdk.capture_exception(e, extra={
            "migration": "007",
            "error": "Failed to run migration"
        })

        return {
            "success": False,
            "error": str(e),
            "message": "Migration 007 failed. Check logs for details."
        }


@router.post("/reset-usage")
async def reset_usage():
    """
    TEMPORARY: Reset monthly usage counter for testing.

    Resets emails_processed_this_month to 0 for all users.

    Usage:
        curl -X POST https://inbox-janitor-production-03fc.up.railway.app/webhooks/reset-usage
    """
    try:
        from sqlalchemy import text, update
        from app.core.database import AsyncSessionLocal
        from app.models.user_settings import UserSettings

        logger.info("Starting usage reset")

        async with AsyncSessionLocal() as session:
            # Reset usage counters
            result = await session.execute(
                update(UserSettings).values(
                    emails_processed_this_month=0,
                    ai_cost_this_month=0.0
                )
            )
            await session.commit()

            rows_updated = result.rowcount

        logger.info(f"Usage reset complete. Updated {rows_updated} users")

        return {
            "success": True,
            "message": "Usage counters reset successfully",
            "users_updated": rows_updated
        }

    except Exception as e:
        logger.error(f"Usage reset failed: {e}", exc_info=True)

        import sentry_sdk
        sentry_sdk.capture_exception(e, extra={
            "error": "Failed to reset usage"
        })

        return {
            "success": False,
            "error": str(e),
            "message": "Usage reset failed. Check logs for details."
        }


@router.post("/sample-and-classify")
async def sample_and_classify(batch_size: int = 250):
    """
    Sample and classify random emails from Gmail backlog.

    Enqueues classification tasks via Celery worker. Call repeatedly to process batches.

    Args:
        batch_size: Number of emails to enqueue (default: 250)

    Returns:
        Current distribution stats and progress

    Usage:
        curl -X POST "https://inbox-janitor-production-03fc.up.railway.app/webhooks/sample-and-classify?batch_size=250"
    """
    try:
        import random
        from sqlalchemy import select, func
        from app.core.database import AsyncSessionLocal
        from app.models.mailbox import Mailbox
        from app.models.email_action import EmailAction
        from app.modules.auth.gmail_oauth import get_gmail_service
        from app.tasks.classify import classify_email_task

        logger.info(f"Sampling: batch_size={batch_size}")

        async with AsyncSessionLocal() as session:
            # Get active mailbox
            result = await session.execute(
                select(Mailbox).where(Mailbox.is_active == True).limit(1)
            )
            mailbox = result.scalar_one_or_none()

            if not mailbox:
                return {"success": False, "error": "No active mailbox found"}

            logger.info(f"Using mailbox: {mailbox.email_address}")

            # Fetch message IDs from Gmail
            logger.info("Fetching message IDs from Gmail...")
            gmail_service = await get_gmail_service(str(mailbox.id))

            message_ids = []
            page_token = None

            # Fetch up to 5,000 message IDs (10 pages * 500)
            for _ in range(10):
                results = gmail_service.users().messages().list(
                    userId='me',
                    maxResults=500,
                    pageToken=page_token
                ).execute()

                messages = results.get('messages', [])
                message_ids.extend([msg['id'] for msg in messages])

                page_token = results.get('nextPageToken')
                if not page_token or len(message_ids) >= 5000:
                    break

            logger.info(f"Fetched {len(message_ids)} message IDs")

            # Random sample for this batch
            sample_ids = random.sample(message_ids, min(batch_size, len(message_ids)))

            # Enqueue classification tasks
            task_ids = []
            for message_id in sample_ids:
                task = classify_email_task.delay(str(mailbox.id), message_id)
                task_ids.append(task.id)

            logger.info(f"Enqueued {len(task_ids)} classification tasks")

            # Get current distribution
            dist_result = await session.execute(
                select(
                    EmailAction.action,
                    func.count(EmailAction.id).label('count')
                ).group_by(EmailAction.action)
            )
            distribution = {row.action: row.count for row in dist_result.all()}

            total = sum(distribution.values())
            percentages = {
                action: f"{(count/total*100):.1f}%" if total > 0 else "0.0%"
                for action, count in distribution.items()
            }

            return {
                "success": True,
                "batch_size": len(sample_ids),
                "tasks_enqueued": len(task_ids),
                "total_classified": total,
                "distribution": distribution,
                "percentages": percentages,
                "message": f"Enqueued {len(task_ids)} tasks. Wait 2-3 minutes, then call again to see updated distribution.",
                "target": "KEEP ~15%, REVIEW ~5%, ARCHIVE ~30%, TRASH ~50%"
            }

    except Exception as e:
        logger.error(f"Sampling failed: {e}", exc_info=True)

        import sentry_sdk
        sentry_sdk.capture_exception(e, extra={
            "batch_size": batch_size,
            "error": "Sampling failed"
        })

        return {
            "success": False,
            "error": str(e),
            "message": "Sampling failed. Check logs for details."
        }
