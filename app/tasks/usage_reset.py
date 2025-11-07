"""
Celery tasks for monthly usage tracking resets.

Runs on the 1st of each month to reset usage counters and send summaries.
"""

import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

from app.core.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.tasks.usage_reset.reset_monthly_usage")
def reset_monthly_usage():
    """
    Reset monthly usage counters for all users.

    Runs on the 1st day of each month at 00:00 UTC.

    Process:
    1. Find all users whose billing period has ended
    2. Send usage summary email
    3. Reset counters (emails_processed_this_month, ai_cost_this_month)
    4. Update billing_period_start to today

    Schedule:
        crontab(day_of_month='1', hour='0', minute='0')
    """
    import asyncio

    logger.info("Starting monthly usage reset task")

    async def _reset():
        from app.core.database import AsyncSessionLocal
        from app.models.user_settings import UserSettings
        from app.models.user import User
        from sqlalchemy import select
        from app.core.email_service import send_usage_summary_email

        today = date.today()
        last_month = today - relativedelta(months=1)
        month_name = last_month.strftime("%B %Y")  # e.g., "November 2025"

        users_reset = 0
        users_failed = 0

        async with AsyncSessionLocal() as session:
            # Get all user_settings
            result = await session.execute(
                select(UserSettings, User)
                .join(User, UserSettings.user_id == User.id)
            )
            user_settings_list = result.all()

            logger.info(f"Found {len(user_settings_list)} users to process")

            for user_settings, user in user_settings_list:
                try:
                    # Check if billing period has ended (1 month passed)
                    billing_period_end = user_settings.current_billing_period_start + relativedelta(months=1)

                    if today >= billing_period_end:
                        # Send usage summary email
                        try:
                            await send_usage_summary_email(
                                user.id,
                                user_settings,
                                month_name
                            )
                        except Exception as email_error:
                            logger.error(
                                f"Failed to send usage summary to user {user.id}: {email_error}",
                                extra={"user_id": str(user.id)}
                            )

                        # Reset counters
                        old_emails_processed = user_settings.emails_processed_this_month
                        old_ai_cost = user_settings.ai_cost_this_month

                        user_settings.emails_processed_this_month = 0
                        user_settings.ai_cost_this_month = 0.0
                        user_settings.current_billing_period_start = today

                        logger.info(
                            f"Reset usage for user {user.id}: "
                            f"{old_emails_processed} emails, ${old_ai_cost:.2f} AI cost",
                            extra={
                                "user_id": str(user.id),
                                "emails_reset": old_emails_processed,
                                "ai_cost_reset": old_ai_cost,
                                "new_billing_period": str(today)
                            }
                        )

                        users_reset += 1

                except Exception as e:
                    logger.error(
                        f"Failed to reset usage for user {user.id}: {e}",
                        extra={"user_id": str(user.id), "error": str(e)}
                    )
                    users_failed += 1

            # Commit all changes
            await session.commit()

        logger.info(
            f"Monthly usage reset complete: {users_reset} users reset, {users_failed} failed",
            extra={
                "users_reset": users_reset,
                "users_failed": users_failed,
                "month": month_name
            }
        )

        return {
            "status": "success",
            "users_reset": users_reset,
            "users_failed": users_failed,
            "month": month_name
        }

    # Run async function
    return asyncio.run(_reset())


@celery_app.task(name="app.tasks.usage_reset.check_billing_periods")
def check_billing_periods():
    """
    Check for users with stale billing periods and reset if needed.

    Runs daily at 02:00 UTC as a safety net in case the monthly task fails.

    This handles edge cases:
    - Users who sign up mid-month (30-day billing period from signup)
    - Monthly task failures
    - Time zone issues
    """
    import asyncio

    logger.info("Checking for stale billing periods")

    async def _check():
        from app.core.database import AsyncSessionLocal
        from app.models.user_settings import UserSettings
        from app.models.user import User
        from sqlalchemy import select
        from dateutil.relativedelta import relativedelta

        today = date.today()
        stale_count = 0

        async with AsyncSessionLocal() as session:
            # Find users whose billing period started >30 days ago
            result = await session.execute(
                select(UserSettings, User)
                .join(User, UserSettings.user_id == User.id)
            )

            for user_settings, user in result.all():
                billing_period_end = user_settings.current_billing_period_start + relativedelta(months=1)

                if today >= billing_period_end:
                    # Reset this user
                    logger.warning(
                        f"Found stale billing period for user {user.id}: "
                        f"started {user_settings.current_billing_period_start}, should reset",
                        extra={
                            "user_id": str(user.id),
                            "billing_period_start": str(user_settings.current_billing_period_start),
                            "days_stale": (today - billing_period_end).days
                        }
                    )

                    # Reset counters
                    user_settings.emails_processed_this_month = 0
                    user_settings.ai_cost_this_month = 0.0
                    user_settings.current_billing_period_start = today

                    stale_count += 1

            if stale_count > 0:
                await session.commit()

        logger.info(
            f"Billing period check complete: {stale_count} stale periods reset",
            extra={"stale_count": stale_count}
        )

        return {
            "status": "success",
            "stale_periods_reset": stale_count
        }

    return asyncio.run(_check())
