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
        from app.core.database import get_async_session
        from app.models.mailbox import Mailbox
        from datetime import datetime

        async with get_async_session() as session:
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
