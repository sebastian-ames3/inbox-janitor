"""Email service for sending transactional emails via Postmark.

Security notes:
- All email headers are sanitized to prevent injection attacks
- Postmark API key stored in environment variables only
- Email addresses validated before sending
- No sensitive data (OAuth tokens, passwords) sent in emails
"""

import re
from typing import Optional
from postmarker.core import PostmarkClient

from app.core.config import settings


def get_postmark_client() -> PostmarkClient:
    """
    Get Postmark API client instance.

    Returns:
        Configured Postmark client

    Raises:
        ValueError: If POSTMARK_API_KEY not configured
    """
    if not settings.POSTMARK_API_KEY:
        raise ValueError("POSTMARK_API_KEY not configured in environment")

    return PostmarkClient(server_token=settings.POSTMARK_API_KEY)


def sanitize_email_header(value: str) -> str:
    """
    Sanitize email header to prevent injection attacks.

    Removes newlines, carriage returns, null bytes, and control characters
    that could be used for header injection.

    Args:
        value: Raw header value

    Returns:
        Sanitized header value

    Example:
        >>> sanitize_email_header("user@example.com\\r\\nBcc: attacker@evil.com")
        'user@example.comBcc: attacker@evil.com'
    """
    # Remove newlines, carriage returns, null bytes
    sanitized = re.sub(r'[\r\n\0]', '', value)

    # Remove other control characters
    sanitized = re.sub(r'[\x00-\x1f\x7f]', '', sanitized)

    # Strip whitespace
    return sanitized.strip()


def validate_email(email: str) -> bool:
    """
    Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        True if email appears valid
    """
    # Simple regex for basic validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


async def send_email(
    to: str,
    subject: str,
    html_body: str,
    text_body: str,
    from_email: Optional[str] = None,
    reply_to: Optional[str] = None,
    tag: Optional[str] = None
) -> bool:
    """
    Send transactional email via Postmark.

    Args:
        to: Recipient email address
        subject: Email subject line
        html_body: HTML version of email body
        text_body: Plain text version of email body
        from_email: Sender email (default: noreply@inboxjanitor.com)
        reply_to: Reply-to address (optional)
        tag: Email tag for tracking (optional)

    Returns:
        True if email sent successfully, False otherwise

    Security:
        - All headers sanitized before sending
        - Email addresses validated
        - Errors logged but not raised (fail gracefully)
        - No sensitive data in email content

    Example:
        >>> await send_email(
        ...     to="user@example.com",
        ...     subject="Welcome!",
        ...     html_body="<h1>Hello</h1>",
        ...     text_body="Hello",
        ...     tag="welcome"
        ... )
        True
    """
    try:
        # Sanitize and validate recipient
        to_sanitized = sanitize_email_header(to)
        if not validate_email(to_sanitized):
            print(f"[Email Service] Invalid email address: {to}")
            return False

        # Sanitize subject
        subject_sanitized = sanitize_email_header(subject)

        # Use default from email if not provided
        if not from_email:
            from_email = settings.FROM_EMAIL or "noreply@inboxjanitor.com"

        from_sanitized = sanitize_email_header(from_email)

        # Sanitize reply-to if provided
        reply_to_sanitized = None
        if reply_to:
            reply_to_sanitized = sanitize_email_header(reply_to)

        # Get Postmark client
        client = get_postmark_client()

        # Send email
        response = client.emails.send(
            From=from_sanitized,
            To=to_sanitized,
            Subject=subject_sanitized,
            HtmlBody=html_body,
            TextBody=text_body,
            ReplyTo=reply_to_sanitized,
            Tag=tag,
            TrackOpens=True,  # Track opens for engagement metrics
            TrackLinks="HtmlOnly"  # Track clicks in HTML emails only
        )

        # Log success
        print(f"[Email Service] Email sent to {to_sanitized}: {subject_sanitized}")
        print(f"[Email Service] Postmark MessageID: {response['MessageID']}")

        return True

    except Exception as e:
        # Log error (but NOT the email content - could contain sensitive data)
        print(f"[Email Service] Failed to send email to {to}: {str(e)}")

        # Report to Sentry if configured
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass  # Sentry not configured, ignore

        return False


async def send_bulk_emails(emails: list[dict]) -> dict:
    """
    Send multiple emails in batch via Postmark.

    More efficient than individual sends for digest/notification emails.

    Args:
        emails: List of email dicts with keys: to, subject, html_body, text_body, tag

    Returns:
        Dict with success count and failed addresses

    Example:
        >>> await send_bulk_emails([
        ...     {"to": "user1@example.com", "subject": "Digest", "html_body": "...", "text_body": "...", "tag": "digest"},
        ...     {"to": "user2@example.com", "subject": "Digest", "html_body": "...", "text_body": "...", "tag": "digest"}
        ... ])
        {'success': 2, 'failed': []}
    """
    try:
        client = get_postmark_client()

        # Build batch payload
        batch = []
        for email in emails:
            # Sanitize each email
            to_sanitized = sanitize_email_header(email['to'])
            if not validate_email(to_sanitized):
                print(f"[Email Service] Skipping invalid email: {email['to']}")
                continue

            batch.append({
                'From': sanitize_email_header(email.get('from_email', settings.FROM_EMAIL or "noreply@inboxjanitor.com")),
                'To': to_sanitized,
                'Subject': sanitize_email_header(email['subject']),
                'HtmlBody': email['html_body'],
                'TextBody': email['text_body'],
                'Tag': email.get('tag', 'bulk'),
                'TrackOpens': True,
                'TrackLinks': 'HtmlOnly'
            })

        # Send batch
        if not batch:
            return {'success': 0, 'failed': []}

        responses = client.emails.send_batch(*batch)

        # Count successes and failures
        success_count = sum(1 for r in responses if r.get('ErrorCode') == 0)
        failed = [r['To'] for r in responses if r.get('ErrorCode') != 0]

        print(f"[Email Service] Bulk send complete: {success_count} success, {len(failed)} failed")

        return {
            'success': success_count,
            'failed': failed
        }

    except Exception as e:
        print(f"[Email Service] Bulk send failed: {str(e)}")
        try:
            import sentry_sdk
            sentry_sdk.capture_exception(e)
        except Exception:
            pass

        return {'success': 0, 'failed': [email['to'] for email in emails]}


# ============================================================================
# High-Level Email Sending Functions
# ============================================================================

async def send_welcome_email(user_email: str, connected_email: str, dashboard_link: str, audit_link: str) -> bool:
    """
    Send welcome email after successful OAuth connection.

    Args:
        user_email: User's email address (same as connected_email for Gmail)
        connected_email: Gmail address that was connected
        dashboard_link: Full URL to settings dashboard
        audit_link: Full URL to audit log

    Returns:
        True if email sent successfully

    Example:
        >>> await send_welcome_email(
        ...     user_email="user@gmail.com",
        ...     connected_email="user@gmail.com",
        ...     dashboard_link="https://app.inboxjanitor.com/dashboard",
        ...     audit_link="https://app.inboxjanitor.com/audit"
        ... )
        True
    """
    from app.modules.digest.templates import format_welcome_email, WELCOME_EMAIL_SUBJECT

    try:
        # Format email content
        html_body, text_body = format_welcome_email({
            'connected_email': connected_email,
            'dashboard_link': dashboard_link,
            'audit_link': audit_link
        })

        # Send email
        success = await send_email(
            to=user_email,
            subject=WELCOME_EMAIL_SUBJECT,
            html_body=html_body,
            text_body=text_body,
            tag='welcome'
        )

        if success:
            print(f"[Digest] Welcome email sent to {user_email}")
        else:
            print(f"[Digest] Failed to send welcome email to {user_email}")

        return success

    except Exception as e:
        print(f"[Digest] Error sending welcome email to {user_email}: {str(e)}")
        return False


async def send_weekly_digest(user_email: str, digest_data: dict) -> bool:
    """
    Send weekly digest email with summary of actions.

    Args:
        user_email: User's email address
        digest_data: Dict with digest data (see DigestData schema)

    Returns:
        True if email sent successfully

    Example:
        >>> await send_weekly_digest(
        ...     user_email="user@gmail.com",
        ...     digest_data={
        ...         'period_start': '2025-01-01',
        ...         'period_end': '2025-01-07',
        ...         'archived_count': 42,
        ...         'trashed_count': 18,
        ...         'kept_count': 5,
        ...         'dashboard_link': 'https://...',
        ...         'audit_link': 'https://...'
        ...     }
        ... )
        True
    """
    from app.modules.digest.templates import format_weekly_digest, WEEKLY_DIGEST_SUBJECT

    try:
        # Format email content
        html_body, text_body = format_weekly_digest(digest_data)

        # Send email
        success = await send_email(
            to=user_email,
            subject=WEEKLY_DIGEST_SUBJECT,
            html_body=html_body,
            text_body=text_body,
            tag='weekly-digest'
        )

        if success:
            print(f"[Digest] Weekly digest sent to {user_email}")
        else:
            print(f"[Digest] Failed to send weekly digest to {user_email}")

        return success

    except Exception as e:
        print(f"[Digest] Error sending weekly digest to {user_email}: {str(e)}")
        return False


async def send_backlog_analysis(user_email: str, backlog_data: dict) -> bool:
    """
    Send backlog analysis email (one-time cleanup offer).

    Args:
        user_email: User's email address
        backlog_data: Dict with backlog data (see BacklogData schema)

    Returns:
        True if email sent successfully

    Example:
        >>> await send_backlog_analysis(
        ...     user_email="user@gmail.com",
        ...     backlog_data={
        ...         'total_old_emails': 5200,
        ...         'promotional_count': 4800,
        ...         'social_count': 400,
        ...         'estimated_cleanup_time': 120,
        ...         'estimated_cleanup_size': 45,
        ...         'cleanup_link': 'https://...',
        ...         'dashboard_link': 'https://...'
        ...     }
        ... )
        True
    """
    from app.modules.digest.templates import format_backlog_analysis, BACKLOG_ANALYSIS_SUBJECT

    try:
        # Format subject with actual count
        subject = BACKLOG_ANALYSIS_SUBJECT.format(promotional_count=backlog_data['promotional_count'])

        # Format email content
        html_body, text_body = format_backlog_analysis(backlog_data)

        # Send email
        success = await send_email(
            to=user_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            tag='backlog-analysis'
        )

        if success:
            print(f"[Digest] Backlog analysis sent to {user_email}")
        else:
            print(f"[Digest] Failed to send backlog analysis to {user_email}")

        return success

    except Exception as e:
        print(f"[Digest] Error sending backlog analysis to {user_email}: {str(e)}")
        return False
