"""
Sentry initialization and error monitoring configuration.

Captures:
- Python exceptions
- FastAPI errors
- Celery task failures
- Custom business logic errors

Context enrichment:
- User ID, mailbox ID, message ID
- Environment (dev/staging/production)
- Release version
"""

import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

from app.core.config import settings

logger = logging.getLogger(__name__)


def init_sentry():
    """
    Initialize Sentry error monitoring.

    Only initializes if SENTRY_DSN is configured.
    Automatically captures FastAPI and Celery errors.
    """
    if not settings.SENTRY_DSN:
        logger.info("Sentry DSN not configured - error monitoring disabled")
        return

    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        release=f"inbox-janitor@0.1.0",  # TODO: Get from git tag or env var

        # Integrations
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            CeleryIntegration(),
            LoggingIntegration(
                level=logging.INFO,  # Capture info and above
                event_level=logging.ERROR,  # Send errors to Sentry
            ),
        ],

        # Performance Monitoring (sample rate)
        traces_sample_rate=0.1 if settings.is_production else 1.0,

        # Error Sampling
        sample_rate=1.0,  # Send all errors

        # Privacy Settings
        send_default_pii=False,  # Don't send user IP, cookies, etc.
        max_breadcrumbs=50,  # Limit breadcrumb history

        # Filter sensitive data
        before_send=filter_sensitive_data,
    )

    logger.info(f"Sentry initialized - environment: {settings.ENVIRONMENT}")


def filter_sensitive_data(event, hint):
    """
    Filter sensitive data before sending to Sentry.

    Removes:
    - OAuth tokens
    - Encryption keys
    - API keys
    - Email body content (should never be in memory, but extra safety)

    Args:
        event: Sentry event dict
        hint: Additional context

    Returns:
        Modified event or None to drop event
    """
    # List of sensitive keys to redact
    sensitive_keys = [
        "access_token",
        "refresh_token",
        "encrypted_access_token",
        "encrypted_refresh_token",
        "token",
        "password",
        "secret",
        "api_key",
        "encryption_key",
        "body",
        "html_body",
        "raw_content",
        "full_message",
    ]

    # Recursively redact sensitive keys
    def redact_dict(obj):
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    obj[key] = "[REDACTED]"
                else:
                    redact_dict(obj[key])
        elif isinstance(obj, list):
            for item in obj:
                redact_dict(item)

    # Apply to event data
    if event.get("extra"):
        redact_dict(event["extra"])

    if event.get("contexts"):
        redact_dict(event["contexts"])

    # Drop events containing body content (should NEVER happen)
    event_str = str(event).lower()
    if "html_body" in event_str or "raw_content" in event_str:
        logger.critical("SECURITY VIOLATION: Body content detected in Sentry event - event dropped")
        return None  # Drop the event

    return event


def capture_business_error(
    error: Exception,
    context: dict,
    level: str = "error"
):
    """
    Capture a business logic error with enriched context.

    Use this for expected errors that need tracking:
    - Classification failures
    - API quota errors
    - Token refresh failures
    - Webhook processing errors

    Args:
        error: The exception that occurred
        context: Dict with business context (mailbox_id, message_id, etc.)
        level: Sentry level (info, warning, error, fatal)

    Example:
        capture_business_error(
            error=e,
            context={
                "mailbox_id": str(mailbox_id),
                "message_id": message_id,
                "operation": "classify_email_tier1",
                "from_address": metadata.from_address,
            },
            level="error"
        )
    """
    # Redact sensitive fields from context
    safe_context = {k: v for k, v in context.items() if "token" not in k.lower()}

    sentry_sdk.capture_exception(
        error,
        level=level,
        extras=safe_context,
    )

    logger.error(
        f"Business error captured: {error}",
        extra=safe_context,
        exc_info=True
    )
