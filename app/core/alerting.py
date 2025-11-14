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
    extra_data: Optional[dict] = None
) -> bool:
    """
    Send alert to admin via multiple channels.

    Args:
        title: Alert title (e.g., "Worker Paused >5 Minutes")
        message: Alert message with details
        severity: "CRITICAL", "HIGH", "MEDIUM", "LOW"
        notify_via: ["email", "sms", "slack"] (default: ["email"])
        extra_data: Additional metadata to include (optional)

    Returns:
        True if alert sent successfully via at least one channel

    Example:
        >>> await send_admin_alert(
        ...     title="🚨 Worker Paused >5 Minutes",
        ...     message="Classification worker paused for 320s. Set WORKER_PAUSED=false to resume.",
        ...     severity="HIGH",
        ...     notify_via=["email"]
        ... )
        True
    """
    if notify_via is None:
        notify_via = ["email"]

    # Build alert payload
    alert = {
        "timestamp": datetime.utcnow().isoformat(),
        "severity": severity,
        "title": title,
        "message": message,
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
