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

    # Detect body content violations (should NEVER happen)
    event_str = str(event).lower()
    if "html_body" in event_str or "raw_content" in event_str:
        logger.critical("SECURITY VIOLATION: Body content detected in Sentry event")

        # Extract forensic metadata
        forensics = {
            "timestamp": event.get("timestamp"),
            "event_id": event.get("event_id"),
            "user_id": event.get("user", {}).get("id") if isinstance(event.get("user"), dict) else None,
            "request_path": event.get("request", {}).get("url") if isinstance(event.get("request"), dict) else None,
            "level": event.get("level"),
            "platform": event.get("platform"),
        }

        # Extract function/line info from exception if available
        if event.get("exception") and isinstance(event.get("exception"), dict):
            values = event["exception"].get("values", [])
            if values and len(values) > 0:
                stacktrace = values[0].get("stacktrace", {})
                frames = stacktrace.get("frames", [])
                if frames and len(frames) > 0:
                    last_frame = frames[-1]
                    forensics["function_name"] = last_frame.get("function")
                    forensics["line_number"] = last_frame.get("lineno")
                    forensics["filename"] = last_frame.get("filename")

        # Store forensics and send admin alert (async, don't block Sentry)
        # We can't use async here, so we'll log to Sentry with a special tag
        # and send alert via a background task
        import asyncio
        try:
            # Try to send alert in background (may not work in sync context)
            asyncio.create_task(_handle_body_content_violation(forensics))
        except RuntimeError:
            # No event loop running - log warning and continue
            logger.error(
                "Cannot send admin alert - no event loop running. "
                "Forensics logged to Sentry.",
                extra=forensics
            )

        # Tag event with security violation marker
        if "tags" not in event:
            event["tags"] = {}
        event["tags"]["security_violation"] = "body_content_detected"

        # Aggressively redact body content
        event = _redact_body_content_from_event(event)

        # Return redacted event (don't drop it - we need visibility)
        return event

    return event


def _redact_body_content_from_event(event):
    """
    Recursively redact body content from Sentry event.

    Args:
        event: Sentry event dict

    Returns:
        Event with body content redacted
    """
    def redact_value(value):
        if isinstance(value, str):
            # Check if string contains body content markers
            if "html_body" in value.lower() or "raw_content" in value.lower():
                return "[REDACTED - BODY CONTENT DETECTED]"
            return value
        elif isinstance(value, dict):
            return {k: redact_value(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [redact_value(item) for item in value]
        else:
            return value

    return redact_value(event)


async def _handle_body_content_violation(forensics: dict):
    """
    Handle body content violation asynchronously.

    Sends admin alert and stores forensics in database.

    Args:
        forensics: Forensic metadata from Sentry event
    """
    from app.core.database import AsyncSessionLocal
    from app.core.alerting import send_admin_alert, record_security_violation

    try:
        # Store in database
        async with AsyncSessionLocal() as session:
            await record_security_violation(
                session=session,
                violation_type="body_content_logged",
                severity="CRITICAL",
                event_metadata=forensics,
                description="Email body content detected in Sentry event"
            )
            await session.commit()

        # Send immediate admin alert
        await send_admin_alert(
            title="🚨 CRITICAL: Email Body Detected in Logs",
            message=f"Body content detected in Sentry event.\n\n"
                    f"Event ID: {forensics.get('event_id', 'N/A')}\n"
                    f"User ID: {forensics.get('user_id', 'N/A')}\n"
                    f"Function: {forensics.get('function_name', 'N/A')}:{forensics.get('line_number', 'N/A')}\n"
                    f"File: {forensics.get('filename', 'N/A')}\n"
                    f"Time: {forensics.get('timestamp', 'N/A')}\n\n"
                    f"IMMEDIATE ACTION REQUIRED:\n"
                    f"1. Review code at {forensics.get('filename')}:{forensics.get('line_number')}\n"
                    f"2. Check for GDPR violation\n"
                    f"3. Determine if user data was exposed\n"
                    f"4. Create incident report",
            severity="CRITICAL",
            notify_via=["email"],  # Future: add "sms" for CRITICAL
            extra_data=forensics
        )

        logger.info("Body content violation alert sent successfully")

    except Exception as e:
        logger.error(f"Failed to handle body content violation: {str(e)}")
        # Don't raise - we don't want to break Sentry error reporting


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
