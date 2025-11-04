"""
Celery tasks for email classification.

Tasks:
- classify_email_tier1: Classify email using metadata-based signals
"""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.classify.classify_email_tier1",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def classify_email_tier1(self, mailbox_id: str, metadata_dict: dict):
    """
    Classify email using Tier 1 (metadata-based) classifier.

    This task is enqueued after metadata extraction completes.

    Flow:
    1. Reconstruct EmailMetadata from dict
    2. Run Tier 1 classifier
    3. Store result in email_actions table
    4. Log classification for learning

    Args:
        mailbox_id: UUID of mailbox (as string)
        metadata_dict: EmailMetadata as dict

    Returns:
        Dict with classification result

    Raises:
        Exception: Retries up to 3 times with exponential backoff

    Usage:
        # Enqueued by process_gmail_history
        classify_email_tier1.delay(mailbox_id, metadata.dict())
    """
    import asyncio

    logger.info(
        f"Classifying email {metadata_dict.get('message_id')} for mailbox {mailbox_id}",
        extra={
            "mailbox_id": mailbox_id,
            "message_id": metadata_dict.get('message_id')
        }
    )

    async def _classify():
        from app.models.email_metadata import EmailMetadata
        from app.modules.classifier.tier1 import classify_email_tier1 as classify_func
        from app.core.database import get_async_session
        from app.models.email_action import EmailAction
        from sqlalchemy import select
        from app.models.mailbox import Mailbox

        try:
            # Reconstruct EmailMetadata from dict
            metadata = EmailMetadata(**metadata_dict)

            # Run classifier
            import time
            start_time = time.time()
            result = classify_func(metadata)
            processing_time_ms = (time.time() - start_time) * 1000

            # Log classification for learning
            from app.core.classification_logger import log_classification
            log_classification(metadata, result, mailbox_id, processing_time_ms)

            logger.info(
                f"Classification result: {result.action.value} "
                f"(confidence={result.confidence:.2f}, overridden={result.overridden})",
                extra={
                    "message_id": metadata.message_id,
                    "action": result.action.value,
                    "confidence": result.confidence,
                    "overridden": result.overridden
                }
            )

            # Store in email_actions table
            async with get_async_session() as session:
                # Verify mailbox exists
                mailbox_result = await session.execute(
                    select(Mailbox).where(Mailbox.id == mailbox_id)
                )
                mailbox = mailbox_result.scalar_one_or_none()

                if not mailbox:
                    logger.error(f"Mailbox {mailbox_id} not found")
                    return {
                        "status": "error",
                        "error": "Mailbox not found"
                    }

                # Create email_action record
                email_action = EmailAction(
                    mailbox_id=UUID(mailbox_id),
                    message_id=metadata.message_id,
                    thread_id=metadata.thread_id,
                    from_address=metadata.from_address,
                    subject=metadata.subject,
                    snippet=metadata.snippet,
                    action=result.action.value,
                    reason=result.reason,
                    confidence=result.confidence,
                    classification_metadata={
                        "signals": [s.dict() for s in result.signals],
                        "overridden": result.overridden,
                        "override_reason": result.override_reason,
                        "tier": "tier_1",
                        "version": "1.0"
                    },
                    can_undo_until=datetime.utcnow() + timedelta(days=30)
                )

                session.add(email_action)
                await session.commit()

                logger.info(
                    f"Stored classification for {metadata.message_id} in email_actions",
                    extra={
                        "message_id": metadata.message_id,
                        "action": result.action.value,
                        "email_action_id": str(email_action.id)
                    }
                )

            return {
                "status": "success",
                "message_id": metadata.message_id,
                "action": result.action.value,
                "confidence": result.confidence,
                "overridden": result.overridden
            }

        except Exception as e:
            logger.error(
                f"Failed to classify email {metadata_dict.get('message_id')}: {e}",
                extra={
                    "mailbox_id": mailbox_id,
                    "message_id": metadata_dict.get('message_id'),
                    "error": str(e)
                }
            )

            # Log to Sentry
            import sentry_sdk
            sentry_sdk.capture_exception(e, extra={
                "mailbox_id": mailbox_id,
                "message_id": metadata_dict.get('message_id'),
                "error": "Classification failed"
            })

            # Retry with exponential backoff
            retry_delay = 30 * (2 ** self.request.retries)
            raise self.retry(exc=e, countdown=retry_delay)

    # Run async function
    return asyncio.run(_classify())


@celery_app.task(name="app.tasks.classify.batch_classify_emails")
def batch_classify_emails(mailbox_id: str, metadata_dicts: list[dict]):
    """
    Classify multiple emails in a batch (for backlog cleanup).

    More efficient than individual tasks for large backlogs.

    Args:
        mailbox_id: UUID of mailbox (as string)
        metadata_dicts: List of EmailMetadata dicts

    Returns:
        Dict with batch processing stats

    Usage:
        # For backlog cleanup
        batch_classify_emails.delay(mailbox_id, [metadata.dict() for metadata in emails])
    """
    import asyncio

    logger.info(
        f"Batch classifying {len(metadata_dicts)} emails for mailbox {mailbox_id}",
        extra={
            "mailbox_id": mailbox_id,
            "batch_size": len(metadata_dicts)
        }
    )

    async def _batch_classify():
        classified_count = 0
        failed_count = 0

        for metadata_dict in metadata_dicts:
            try:
                # Enqueue individual classification task
                classify_email_tier1.delay(mailbox_id, metadata_dict)
                classified_count += 1

            except Exception as e:
                failed_count += 1
                logger.error(
                    f"Failed to enqueue classification for {metadata_dict.get('message_id')}: {e}"
                )

        logger.info(
            f"Batch classification complete: {classified_count} enqueued, {failed_count} failed",
            extra={
                "mailbox_id": mailbox_id,
                "classified": classified_count,
                "failed": failed_count
            }
        )

        return {
            "status": "success",
            "enqueued": classified_count,
            "failed": failed_count,
            "total": len(metadata_dicts)
        }

    # Run async function
    return asyncio.run(_batch_classify())
