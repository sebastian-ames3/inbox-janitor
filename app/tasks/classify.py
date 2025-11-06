"""
Celery tasks for email classification.

Tasks:
- classify_email_tier1: Classify email using metadata-based signals (with AI fallback)
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
    Classify email using Tier 1 (metadata-based) classifier with AI fallback.

    This task is enqueued after metadata extraction completes.

    Flow:
    1. Reconstruct EmailMetadata from dict
    2. Run Tier 1 classifier
    3. If confidence < threshold, run Tier 2 (AI) classifier
    4. Check usage limits
    5. Store result in email_actions table
    6. Log classification for learning

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

            # Run Tier 1 classifier
            import time
            start_time = time.time()
            tier1_result = classify_func(metadata)
            tier1_time = time.time() - start_time

            # Check if AI fallback needed (Tier 1 confidence < threshold)
            from app.core.config import settings

            tier2_result = None  # Track if tier2 was used
            ai_cost = 0.0  # Track AI API cost

            if tier1_result.confidence < settings.AI_CONFIDENCE_THRESHOLD:
                logger.info(
                    f"Tier 1 confidence {tier1_result.confidence:.2f} < {settings.AI_CONFIDENCE_THRESHOLD}, "
                    f"calling AI classifier for {metadata.message_id}",
                    extra={
                        "message_id": metadata.message_id,
                        "tier1_confidence": tier1_result.confidence
                    }
                )

                # Run Tier 2 (AI) classifier
                from app.modules.classifier.tier2_ai import (
                    classify_email_tier2,
                    combine_tier1_tier2_results
                )

                tier2_start = time.time()
                tier2_result = await classify_email_tier2(metadata)
                tier2_time = time.time() - tier2_start

                # Track AI cost (if available in tier2_result metadata)
                if hasattr(tier2_result, 'cost'):
                    ai_cost = tier2_result.cost
                elif 'cost' in tier2_result.signals[0].metadata if tier2_result.signals else {}:
                    ai_cost = tier2_result.signals[0].metadata.get('cost', 0.0)

                # Combine Tier 1 + Tier 2 results
                result = combine_tier1_tier2_results(tier1_result, tier2_result)

                processing_time_ms = (tier1_time + tier2_time) * 1000

                logger.info(
                    f"Combined Tier 1 + Tier 2 result: {result.action.value} "
                    f"(Tier 1: {tier1_result.confidence:.2f}, Tier 2: {tier2_result.confidence:.2f}, "
                    f"Combined: {result.confidence:.2f}, AI cost: ${ai_cost:.4f})",
                    extra={
                        "message_id": metadata.message_id,
                        "tier1_action": tier1_result.action.value,
                        "tier1_confidence": tier1_result.confidence,
                        "tier2_action": tier2_result.action.value,
                        "tier2_confidence": tier2_result.confidence,
                        "combined_action": result.action.value,
                        "combined_confidence": result.confidence,
                        "ai_cost": ai_cost
                    }
                )
            else:
                # Tier 1 confidence high enough, use Tier 1 result
                result = tier1_result
                processing_time_ms = tier1_time * 1000

                logger.info(
                    f"Tier 1 confidence {tier1_result.confidence:.2f} >= {settings.AI_CONFIDENCE_THRESHOLD}, "
                    f"skipping AI classifier",
                    extra={
                        "message_id": metadata.message_id,
                        "tier1_confidence": tier1_result.confidence
                    }
                )

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

            # Store in email_actions table and check usage limits
            async with get_async_session() as session:
                # Verify mailbox exists and get user settings
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

                # Get user settings for usage tracking
                from app.models.user_settings import UserSettings
                user_settings_result = await session.execute(
                    select(UserSettings).where(UserSettings.user_id == mailbox.user_id)
                )
                user_settings = user_settings_result.scalar_one_or_none()

                if not user_settings:
                    logger.error(f"User settings not found for user {mailbox.user_id}")
                    return {
                        "status": "error",
                        "error": "User settings not found"
                    }

                # Check monthly limit BEFORE processing
                if user_settings.has_reached_monthly_limit:
                    logger.warning(
                        f"User {mailbox.user_id} has reached monthly limit "
                        f"({user_settings.emails_processed_this_month}/{user_settings.monthly_email_limit})",
                        extra={
                            "user_id": str(mailbox.user_id),
                            "emails_processed": user_settings.emails_processed_this_month,
                            "limit": user_settings.monthly_email_limit
                        }
                    )

                    # Send limit reached notification
                    from app.core.email_service import send_usage_limit_reached_email
                    await send_usage_limit_reached_email(mailbox.user_id, user_settings)

                    return {
                        "status": "limit_reached",
                        "message": "Monthly email processing limit reached",
                        "emails_processed": user_settings.emails_processed_this_month,
                        "limit": user_settings.monthly_email_limit
                    }

                # Check if approaching limit (80%+) and send warning
                if user_settings.is_approaching_limit and user_settings.emails_processed_this_month % 100 == 0:
                    # Only send every 100 emails to avoid spam
                    logger.info(
                        f"User {mailbox.user_id} approaching monthly limit "
                        f"({user_settings.usage_percentage:.1f}%)",
                        extra={
                            "user_id": str(mailbox.user_id),
                            "usage_percentage": user_settings.usage_percentage
                        }
                    )

                    from app.core.email_service import send_usage_warning_email
                    await send_usage_warning_email(mailbox.user_id, user_settings)

                # Determine which tier was used
                ai_used = tier2_result is not None
                tier_label = "tier_1_and_tier_2" if ai_used else "tier_1"

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
                        "tier": tier_label,
                        "ai_used": ai_used,
                        "tier1_confidence": tier1_result.confidence,
                        "tier2_confidence": tier2_result.confidence if tier2_result else None,
                        "ai_cost": ai_cost if ai_used else 0.0,
                        "version": "1.0"
                    },
                    can_undo_until=datetime.utcnow() + timedelta(days=30)
                )

                session.add(email_action)

                # Update usage tracking
                user_settings.emails_processed_this_month += 1

                # Track AI cost if AI was used
                if ai_used and ai_cost > 0:
                    user_settings.ai_cost_this_month += ai_cost

                await session.commit()

                logger.info(
                    f"Stored classification for {metadata.message_id} in email_actions "
                    f"(usage: {user_settings.emails_processed_this_month}/{user_settings.monthly_email_limit}, "
                    f"AI cost: ${user_settings.ai_cost_this_month:.4f})",
                    extra={
                        "message_id": metadata.message_id,
                        "action": result.action.value,
                        "email_action_id": str(email_action.id),
                        "emails_processed": user_settings.emails_processed_this_month,
                        "monthly_limit": user_settings.monthly_email_limit,
                        "ai_cost_this_month": user_settings.ai_cost_this_month
                    }
                )

            return {
                "status": "success",
                "message_id": metadata.message_id,
                "action": result.action.value,
                "confidence": result.confidence,
                "overridden": result.overridden,
                "ai_used": ai_used,
                "ai_cost": ai_cost if ai_used else 0.0
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
            from app.core.sentry import capture_business_error
            capture_business_error(e, context={
                "mailbox_id": mailbox_id,
                "message_id": metadata_dict.get('message_id'),
                "error": "Classification failed",
                "retry_count": self.request.retries,
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
