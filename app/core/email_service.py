"""
Email notification service for usage limits and warnings.

Sends emails via Postmark when users approach or reach monthly limits.

TODO: Integrate with Postmark API once templates are created.
"""

import logging
from typing import Optional
from uuid import UUID

logger = logging.getLogger(__name__)


async def send_usage_warning_email(user_id: UUID, user_settings) -> bool:
    """
    Send email when user reaches 80% of monthly limit.

    Args:
        user_id: User UUID
        user_settings: UserSettings object with usage data

    Returns:
        True if email sent successfully, False otherwise

    Email content:
        Subject: You're approaching your monthly email limit
        Body:
            Hi there,

            You've processed {emails_processed} of your {limit} emails this month ({percentage}%).

            Plan: {plan_tier}
            Emails remaining: {remaining}

            To avoid hitting your limit:
            - Upgrade to Pro ($12/mo) for 25,000 emails
            - Or wait until {next_billing_date} when your limit resets

            [Upgrade to Pro]

            Questions? Reply to this email.
    """
    emails_processed = user_settings.emails_processed_this_month
    limit = user_settings.monthly_email_limit
    percentage = user_settings.usage_percentage
    remaining = user_settings.emails_remaining_this_month
    plan_tier = user_settings.plan_tier

    logger.info(
        f"Would send usage warning email to user {user_id}: "
        f"{emails_processed}/{limit} ({percentage:.1f}%)",
        extra={
            "user_id": str(user_id),
            "emails_processed": emails_processed,
            "limit": limit,
            "percentage": percentage,
            "plan_tier": plan_tier
        }
    )

    # TODO: Implement actual email sending via Postmark
    # For now, just log
    # from postmarker.core import PostmarkClient
    # postmark = PostmarkClient(server_token=settings.POSTMARK_API_KEY)
    # postmark.emails.send(...)

    return True


async def send_usage_limit_reached_email(user_id: UUID, user_settings) -> bool:
    """
    Send email when user reaches 100% of monthly limit.

    Args:
        user_id: User UUID
        user_settings: UserSettings object with usage data

    Returns:
        True if email sent successfully, False otherwise

    Email content:
        Subject: Monthly email limit reached
        Body:
            Hi there,

            You've reached your monthly limit of {limit} emails on the {plan_tier} plan.

            We've paused email processing until {next_billing_date} when your limit resets.

            To continue processing emails now:
            - Upgrade to Pro ($12/mo) for 25,000 emails/month
            - Or upgrade to Business ($30/mo) for 100,000 emails/month

            [Upgrade Now]

            Your existing emails are safe - we've just paused classification until next month.

            Questions? Reply to this email.
    """
    limit = user_settings.monthly_email_limit
    plan_tier = user_settings.plan_tier

    logger.warning(
        f"Would send limit reached email to user {user_id}: "
        f"Limit {limit} reached on {plan_tier} plan",
        extra={
            "user_id": str(user_id),
            "limit": limit,
            "plan_tier": plan_tier
        }
    )

    # TODO: Implement actual email sending via Postmark
    # For now, just log
    # from postmarker.core import PostmarkClient
    # postmark = PostmarkClient(server_token=settings.POSTMARK_API_KEY)
    # postmark.emails.send(...)

    return True


async def send_usage_summary_email(user_id: UUID, user_settings, month_name: str) -> bool:
    """
    Send monthly usage summary at billing period end.

    Args:
        user_id: User UUID
        user_settings: UserSettings object with usage data
        month_name: Name of month (e.g., "November 2025")

    Returns:
        True if email sent successfully, False otherwise

    Email content:
        Subject: Your November email processing summary
        Body:
            Hi there,

            Here's your email processing summary for {month}:

            📊 Usage Stats:
            - Emails processed: {emails_processed}
            - AI classifications: {ai_percentage}%
            - AI cost: ${ai_cost}

            💰 Your Plan:
            - {plan_tier}: {limit} emails/month
            - You used {percentage}% of your limit

            Your limit resets today! All counters are now at 0.

            Need more emails? Upgrade anytime:
            [View Plans]
    """
    emails_processed = user_settings.emails_processed_this_month
    limit = user_settings.monthly_email_limit
    percentage = user_settings.usage_percentage
    ai_cost = user_settings.ai_cost_this_month
    plan_tier = user_settings.plan_tier

    # Estimate AI percentage (rough calculation)
    # Assuming 30% of emails use AI on average
    ai_percentage = 30.0  # Placeholder

    logger.info(
        f"Would send usage summary email to user {user_id} for {month_name}: "
        f"{emails_processed}/{limit} emails, ${ai_cost:.2f} AI cost",
        extra={
            "user_id": str(user_id),
            "month": month_name,
            "emails_processed": emails_processed,
            "limit": limit,
            "ai_cost": ai_cost,
            "plan_tier": plan_tier
        }
    )

    # TODO: Implement actual email sending via Postmark
    return True
