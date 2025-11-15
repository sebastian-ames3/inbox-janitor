"""
Admin alerting system for security and operational events.

Sends immediate notifications to admin when critical events occur:
- Security violations (body content logged, token exposed)
- Operational issues (worker paused >5 min, high undo rate)
- Service degradation (inactive mailboxes, rate limiting)

Security notes:
- Alerts may contain sensitive metadata, but never full email bodies or tokens
- Alert delivery failures logged to Sentry as fallback
- All alerts preserved in security_violations table for forensics
"""

import os
import logging
from datetime import datetime
from typing import Optional, List
from uuid import UUID

import sentry_sdk
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.digest.email_service import send_email

logger = logging.getLogger(__name__)


async def send_admin_alert(
    title: str,
    message: str,
    severity: str = "MEDIUM",
    notify_via: Optional[List[str]] = None,
    extra_data: Optional[dict] = None,
    rate_limit_seconds: int = 300  # Default: 5 minutes between same alert
) -> bool:
    """
    Send alert to admin via multiple channels with rate limiting.

    Deduplicates alerts by title - only sends once per rate_limit_seconds.
    This prevents alert spam when the same issue triggers multiple times.

    Args:
        title: Alert title (e.g., "Worker Paused >5 Minutes")
        message: Alert message with details
        severity: "CRITICAL", "HIGH", "MEDIUM", "LOW"
        notify_via: ["email", "sms", "slack"] (default: ["email"])
        extra_data: Additional metadata to include (optional)
        rate_limit_seconds: Minimum seconds between sending same alert (default: 300)

    Returns:
        True if alert sent successfully via at least one channel

    Example:
        >>> await send_admin_alert(
        ...     title="🚨 Worker Paused >5 Minutes",
        ...     message="Classification worker paused for 320s. Set WORKER_PAUSED=false to resume.",
        ...     severity="HIGH",
        ...     notify_via=["email"],
        ...     rate_limit_seconds=300  # Only send once per 5 minutes
        ... )
        True
    """
    if notify_via is None:
        notify_via = ["email"]

    # Check if we've sent this alert recently (rate limiting)
    from app.core.config import settings
    import redis

    try:
        redis_client = redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=2)

        # Create unique key for this alert type
        alert_key = f"admin_alert:{title}"

        # Check if this alert was sent recently
        if redis_client.get(alert_key):
            logger.info(
                f"Rate limiting: Alert '{title}' already sent within {rate_limit_seconds}s, skipping",
                extra={"title": title, "rate_limit_seconds": rate_limit_seconds}
            )
            redis_client.close()
            return False  # Alert rate-limited

        # Set the rate limit key (expires after rate_limit_seconds)
        redis_client.setex(alert_key, rate_limit_seconds, "1")
        redis_client.close()

    except Exception as e:
        # If Redis fails, still send the alert (fail open, not closed)
        logger.warning(f"Redis rate limiting check failed, sending alert anyway: {e}")
        pass

    # Build alert payload
    # Note: Don't use 'message' key in extra - conflicts with logging.LogRecord
    alert = {
        "timestamp": datetime.utcnow().isoformat(),
        "severity": severity,
        "title": title,
        "alert_message": message,  # Renamed from 'message' to avoid logging conflict
        "environment": os.getenv("ENVIRONMENT", "production"),
    }

    if extra_data:
        alert["extra_data"] = extra_data

    # Log to application logs
    logger.warning(
        f"[{severity}] {title}",
        extra=alert
    )

    # Send to Sentry for centralized monitoring
    sentry_sdk.capture_message(
        f"[{severity}] {title}",
        level=_get_sentry_level(severity),
        extras=alert
    )

    success = False

    # Send email
    if "email" in notify_via:
        success = await _send_admin_email(title, message, severity, alert) or success

    # Future: Add SMS via Twilio
    if "sms" in notify_via and severity == "CRITICAL":
        # TODO: Implement Twilio integration
        logger.info("SMS alerts not yet implemented - would send SMS for CRITICAL alert")
        pass

    # Future: Add Slack via webhook
    if "slack" in notify_via:
        # TODO: Implement Slack integration
        logger.info("Slack alerts not yet implemented - would send Slack message")
        pass

    return success


async def _send_admin_email(
    title: str,
    message: str,
    severity: str,
    alert_data: dict
) -> bool:
    """
    Send admin alert email.

    Args:
        title: Alert title
        message: Alert message
        severity: Alert severity
        alert_data: Full alert payload

    Returns:
        True if email sent successfully
    """
    admin_email = os.getenv("ADMIN_EMAIL")
    if not admin_email:
        logger.error("ADMIN_EMAIL not configured - cannot send admin alert email")
        return False

    # Format email content
    html_body = _format_admin_alert_html(title, message, severity, alert_data)
    text_body = _format_admin_alert_text(title, message, severity, alert_data)

    try:
        success = await send_email(
            to=admin_email,
            subject=f"[{severity}] {title}",
            html_body=html_body,
            text_body=text_body,
            tag="admin-alert"
        )

        if success:
            logger.info(f"Admin alert email sent to {admin_email}: {title}")
        else:
            logger.error(f"Failed to send admin alert email to {admin_email}: {title}")

        return success

    except Exception as e:
        logger.error(f"Error sending admin alert email: {str(e)}")
        sentry_sdk.capture_exception(e)
        return False


def _format_admin_alert_html(title: str, message: str, severity: str, alert_data: dict) -> str:
    """Format admin alert email as HTML."""
    severity_color = {
        "CRITICAL": "#DC2626",  # Red
        "HIGH": "#EA580C",      # Orange
        "MEDIUM": "#D97706",    # Amber
        "LOW": "#65A30D"        # Green
    }.get(severity, "#6B7280")

    html = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #1F2937;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .alert-header {{
                background-color: {severity_color};
                color: white;
                padding: 20px;
                border-radius: 8px 8px 0 0;
                margin-bottom: 0;
            }}
            .alert-header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .alert-body {{
                background-color: #F9FAFB;
                padding: 20px;
                border: 1px solid #E5E7EB;
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
            .message {{
                background-color: white;
                padding: 16px;
                border-radius: 6px;
                border-left: 4px solid {severity_color};
                margin: 16px 0;
                white-space: pre-wrap;
            }}
            .metadata {{
                font-size: 12px;
                color: #6B7280;
                margin-top: 20px;
                padding-top: 16px;
                border-top: 1px solid #E5E7EB;
            }}
            .metadata strong {{
                color: #374151;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #E5E7EB;
                font-size: 12px;
                color: #6B7280;
            }}
        </style>
    </head>
    <body>
        <div class="alert-header">
            <h1>{title}</h1>
        </div>
        <div class="alert-body">
            <div class="message">{message}</div>

            <div class="metadata">
                <p><strong>Severity:</strong> {severity}</p>
                <p><strong>Environment:</strong> {alert_data.get('environment', 'production')}</p>
                <p><strong>Timestamp:</strong> {alert_data.get('timestamp', 'N/A')}</p>
            </div>
        </div>

        <div class="footer">
            <p>This is an automated alert from Inbox Janitor monitoring system.</p>
            <p>To configure alert settings, update ADMIN_EMAIL in Railway environment variables.</p>
        </div>
    </body>
    </html>
    """
    return html


def _format_admin_alert_text(title: str, message: str, severity: str, alert_data: dict) -> str:
    """Format admin alert email as plain text."""
    text = f"""
[{severity}] {title}

{message}

---
Severity: {severity}
Environment: {alert_data.get('environment', 'production')}
Timestamp: {alert_data.get('timestamp', 'N/A')}

---
This is an automated alert from Inbox Janitor monitoring system.
To configure alert settings, update ADMIN_EMAIL in Railway environment variables.
    """
    return text.strip()


def _get_sentry_level(severity: str) -> str:
    """
    Map alert severity to Sentry log level.

    Args:
        severity: Alert severity (CRITICAL, HIGH, MEDIUM, LOW)

    Returns:
        Sentry log level (error, warning, info)
    """
    mapping = {
        "CRITICAL": "error",
        "HIGH": "error",
        "MEDIUM": "warning",
        "LOW": "info"
    }
    return mapping.get(severity, "warning")


# ============================================================================
# Database Functions for Security Violations Tracking
# ============================================================================

async def record_security_violation(
    session: AsyncSession,
    violation_type: str,
    severity: str,
    event_metadata: dict,
    description: Optional[str] = None
) -> UUID:
    """
    Record security violation in database for forensics.

    Args:
        session: Database session
        violation_type: Type of violation (e.g., 'body_content_logged', 'token_exposed')
        severity: Violation severity (CRITICAL, HIGH, MEDIUM, LOW)
        event_metadata: Forensic metadata (will be encrypted)
        description: Optional description of the violation

    Returns:
        UUID of created security_violations record

    Example:
        >>> await record_security_violation(
        ...     session=session,
        ...     violation_type="body_content_logged",
        ...     severity="CRITICAL",
        ...     event_metadata={
        ...         "event_id": "abc123",
        ...         "user_id": "user-456",
        ...         "function_name": "classify_email",
        ...         "line_number": 123
        ...     },
        ...     description="Email body detected in Sentry event"
        ... )
        UUID('...')
    """
    from app.models.security_violations import SecurityViolation

    violation = SecurityViolation(
        violation_type=violation_type,
        severity=severity,
        event_metadata=event_metadata,  # PostgreSQL JSONB column
        description=description
    )

    session.add(violation)
    await session.flush()

    logger.critical(
        f"Security violation recorded: {violation_type} ({severity})",
        extra={
            "violation_id": str(violation.id),
            "violation_type": violation_type,
            "severity": severity
        }
    )

    return violation.id


async def record_worker_pause_event(
    session: AsyncSession,
    mailbox_id: Optional[UUID],
    message_id: Optional[str]
) -> UUID:
    """
    Record worker pause event in database.

    Args:
        session: Database session
        mailbox_id: Mailbox that triggered the pause check (optional)
        message_id: Message that was skipped (optional)

    Returns:
        UUID of created worker_pause_events record

    Example:
        >>> await record_worker_pause_event(
        ...     session=session,
        ...     mailbox_id=UUID('...'),
        ...     message_id='gmail-msg-123'
        ... )
        UUID('...')
    """
    from app.models.worker_pause_events import WorkerPauseEvent

    event = WorkerPauseEvent(
        mailbox_id=mailbox_id,
        message_id=message_id,
        skipped_count=1
    )

    session.add(event)
    await session.flush()

    logger.warning(
        f"Worker pause event recorded",
        extra={
            "event_id": str(event.id),
            "mailbox_id": str(mailbox_id) if mailbox_id else None,
            "message_id": message_id
        }
    )

    return event.id


async def check_worker_paused(
    session: AsyncSession,
    mailbox_id: Optional[UUID],
    message_id: Optional[str]
) -> bool:
    """
    Check if worker is paused and handle monitoring/alerting.

    If paused:
    - Record pause event in database
    - Check how long worker has been paused
    - Send admin alert if paused >5 minutes

    Args:
        session: Database session
        mailbox_id: Mailbox attempting classification
        message_id: Message being skipped

    Returns:
        True if worker is paused, False otherwise

    Example:
        >>> is_paused = await check_worker_paused(session, mailbox_id, message_id)
        >>> if is_paused:
        ...     return {"status": "paused"}
    """
    import os
    from datetime import datetime, timedelta
    from sqlalchemy import select, func
    from app.models.worker_pause_events import WorkerPauseEvent

    if os.getenv('WORKER_PAUSED', 'false').lower() != 'true':
        return False  # Not paused

    # Worker is paused - record event
    await record_worker_pause_event(session, mailbox_id, message_id)

    # Check how long worker has been paused
    # Find oldest active (unresolved) pause event
    result = await session.execute(
        select(WorkerPauseEvent)
        .where(WorkerPauseEvent.resumed_at.is_(None))
        .order_by(WorkerPauseEvent.paused_at.asc())
        .limit(1)
    )
    oldest_pause = result.scalar_one_or_none()

    if oldest_pause:
        pause_duration = oldest_pause.duration_seconds

        # Alert admin if paused >5 minutes
        if pause_duration > 300:  # 5 minutes
            await send_admin_alert(
                title="🚨 Worker Paused >5 Minutes",
                message=f"Classification worker paused for {pause_duration:.0f} seconds.\n\n"
                        f"Set WORKER_PAUSED=false in Railway environment variables to resume.\n\n"
                        f"Emails are being skipped and will need reprocessing when worker resumes.",
                severity="HIGH",
                extra_data={
                    "pause_duration_seconds": pause_duration,
                    "mailbox_id": str(mailbox_id) if mailbox_id else None,
                    "message_id": message_id
                }
            )

    logger.warning(
        f"Worker paused - classification skipped",
        extra={
            "mailbox_id": str(mailbox_id) if mailbox_id else None,
            "message_id": message_id
        }
    )

    return True  # Worker is paused


async def handle_inactive_mailbox(
    session: AsyncSession,
    mailbox_id: UUID,
    user_id: UUID,
    user_email: str
) -> None:
    """
    Handle inactive mailbox during watch registration.

    Actions:
    - Send email to user: "Gmail connection inactive - please reconnect"
    - Alert admin if >10 mailboxes inactive (mass issue)
    - Log for monitoring

    Args:
        session: Database session
        mailbox_id: ID of inactive mailbox
        user_id: ID of user who owns the mailbox
        user_email: User's email address

    Example:
        >>> await handle_inactive_mailbox(
        ...     session=session,
        ...     mailbox_id=UUID('...'),
        ...     user_id=UUID('...'),
        ...     user_email='user@gmail.com'
        ... )
    """
    from sqlalchemy import select, func
    from app.models.mailbox import Mailbox
    from app.modules.digest.email_service import send_email

    logger.warning(
        f"Mailbox inactive - watch registration skipped",
        extra={
            "mailbox_id": str(mailbox_id),
            "user_id": str(user_id)
        }
    )

    # Send email to user
    html_body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                line-height: 1.6;
                color: #1F2937;
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .warning-header {{
                background-color: #F59E0B;
                color: white;
                padding: 20px;
                border-radius: 8px 8px 0 0;
            }}
            .warning-header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .warning-body {{
                background-color: #F9FAFB;
                padding: 20px;
                border: 1px solid #E5E7EB;
                border-top: none;
                border-radius: 0 0 8px 8px;
            }}
            .button {{
                display: inline-block;
                background-color: #3B82F6;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 6px;
                margin: 16px 0;
            }}
            .footer {{
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #E5E7EB;
                font-size: 12px;
                color: #6B7280;
            }}
        </style>
    </head>
    <body>
        <div class="warning-header">
            <h1>⚠️ Gmail Connection Needs Attention</h1>
        </div>
        <div class="warning-body">
            <p>Your Gmail connection to Inbox Janitor has become inactive.</p>

            <p>This means:</p>
            <ul>
                <li>Real-time email classification is paused</li>
                <li>New emails won't be automatically processed</li>
                <li>Your inbox cleanup is temporarily disabled</li>
            </ul>

            <p>To resume automatic email management, please reconnect your Gmail account:</p>

            <a href="{settings.APP_URL}/auth/gmail" class="button">Reconnect Gmail</a>

            <p>If you need help, reply to this email or contact support at support@inboxjanitor.app</p>
        </div>

        <div class="footer">
            <p>Inbox Janitor - Automatic email hygiene that respects your privacy</p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
Gmail Connection Needs Attention

Your Gmail connection to Inbox Janitor has become inactive.

This means:
- Real-time email classification is paused
- New emails won't be automatically processed
- Your inbox cleanup is temporarily disabled

To resume automatic email management, please reconnect your Gmail account:
{settings.APP_URL}/auth/gmail

If you need help, reply to this email or contact support at support@inboxjanitor.app

---
Inbox Janitor - Automatic email hygiene that respects your privacy
    """

    try:
        await send_email(
            to=user_email,
            subject="Inbox Janitor: Gmail connection needs attention",
            html_body=html_body,
            text_body=text_body,
            tag="mailbox-inactive"
        )
        logger.info(f"Inactive mailbox notification sent to {user_email}")
    except Exception as e:
        logger.error(f"Failed to send inactive mailbox email to {user_email}: {str(e)}")
        # Don't raise - this is a notification, not critical

    # Check if this is a mass issue
    result = await session.execute(
        select(func.count(Mailbox.id)).where(Mailbox.is_active == False)
    )
    inactive_count = result.scalar()

    if inactive_count > 10:
        await send_admin_alert(
            title="⚠️ Mass Mailbox Inactivity",
            message=f"{inactive_count} mailboxes are currently inactive.\n\n"
                    f"This may indicate:\n"
                    f"- OAuth token refresh issue\n"
                    f"- Gmail API outage\n"
                    f"- Systematic authentication problem\n\n"
                    f"Check Railway logs for token refresh errors.",
            severity="HIGH",
            extra_data={
                "inactive_count": inactive_count,
                "latest_inactive_mailbox": str(mailbox_id)
            }
        )
