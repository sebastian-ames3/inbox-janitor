"""Email service for sending transactional emails via Postmark.

Security notes:
- All email headers are sanitized to prevent injection attacks
- Postmark API key stored in environment variables only
- Email addresses validated before sending
- No sensitive data (OAuth tokens, passwords) sent in emails
"""

import re
from typing import Optional, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from postmarker.core import PostmarkClient
import html2text

from app.core.config import settings


# Initialize Jinja2 environment for email templates
_template_env = None

def get_template_env() -> Environment:
    """Get or create Jinja2 environment for email templates."""
    global _template_env
    if _template_env is None:
        template_dir = Path(__file__).parent.parent.parent / "templates" / "emails"
        _template_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
    return _template_env


def render_email_template(template_name: str, data: Dict[str, Any]) -> tuple[str, str]:
    """
    Render email template (HTML + text version).

    Args:
        template_name: Template filename (e.g., "token_refresh_retry.html")
        data: Template variables dict

    Returns:
        Tuple of (html_body, text_body)
    """
    env = get_template_env()
    template = env.get_template(template_name)
    html_body = template.render(**data)

    # Convert HTML to plain text for text_body
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 78
    text_body = h.handle(html_body)

    return html_body, text_body


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
    import asyncio

    def _send_email_sync():
        """Synchronous email sending function to run in thread pool."""
        try:
            # Sanitize and validate recipient
            to_sanitized = sanitize_email_header(to)
            if not validate_email(to_sanitized):
                print(f"[Email Service] Invalid email address: {to}")
                return False

            # Sanitize subject
            subject_sanitized = sanitize_email_header(subject)

            # Use default from email if not provided
            nonlocal from_email
            if not from_email:
                from_email = settings.FROM_EMAIL or "noreply@inboxjanitor.com"

            from_sanitized = sanitize_email_header(from_email)

            # Sanitize reply-to if provided
            reply_to_sanitized = None
            if reply_to:
                reply_to_sanitized = sanitize_email_header(reply_to)

            # Get Postmark client
            client = get_postmark_client()

            # Send email (synchronous call)
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

    # Run synchronous Postmark call in thread pool to avoid blocking event loop
    try:
        return await asyncio.to_thread(_send_email_sync)
    except AttributeError:
        # Python <3.9 doesn't have asyncio.to_thread, fall back to run_in_executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_email_sync)


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
    import asyncio

    def _send_bulk_emails_sync():
        """Synchronous bulk email sending function to run in thread pool."""
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

    # Run synchronous Postmark call in thread pool to avoid blocking event loop
    try:
        return await asyncio.to_thread(_send_bulk_emails_sync)
    except AttributeError:
        # Python <3.9 doesn't have asyncio.to_thread, fall back to run_in_executor
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _send_bulk_emails_sync)


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

# ============================================================================
# Token Refresh Email Functions (PRD-0007)
# ============================================================================

async def send_token_refresh_retry_email(user_email: str, mailbox_email: str, attempt: int) -> bool:
    """
    Send gentle warning email on 2nd token refresh failure.

    Args:
        user_email: User's email address  
        mailbox_email: Gmail address having connection issues
        attempt: Attempt number (should be 2)

    Returns:
        True if email sent successfully

    Example:
        >>> await send_token_refresh_retry_email(
        ...     user_email="user@example.com",
        ...     mailbox_email="work@gmail.com",
        ...     attempt=2
        ... )
        True
    """
    try:
        html_body, text_body = render_email_template(
            "token_refresh_retry.html",
            {
                "mailbox_email": mailbox_email,
                "attempt": attempt,
                "next_retry": "in a few moments"
            }
        )

        success = await send_email(
            to=user_email,
            subject="Inbox Janitor: Having trouble connecting to Gmail",
            html_body=html_body,
            text_body=text_body,
            tag='token-refresh-retry'
        )

        if success:
            print(f"[OAuth] Token refresh retry email sent to {user_email} (mailbox: {mailbox_email})")
        else:
            print(f"[OAuth] Failed to send token refresh retry email to {user_email}")

        return success

    except Exception as e:
        print(f"[OAuth] Error sending token refresh retry email to {user_email}: {str(e)}")
        return False


async def send_token_refresh_final_failure_email(
    user_email: str,
    mailbox_email: str,
    failure_count: int,
    reconnect_url: str
) -> bool:
    """
    Send urgent email after 3rd token refresh failure (mailbox disabled).

    Args:
        user_email: User's email address
        mailbox_email: Gmail address that was disabled
        failure_count: Number of failed attempts (should be 3)
        reconnect_url: Full URL to reconnect Gmail

    Returns:
        True if email sent successfully

    Example:
        >>> await send_token_refresh_final_failure_email(
        ...     user_email="user@example.com",
        ...     mailbox_email="work@gmail.com",
        ...     failure_count=3,
        ...     reconnect_url="https://app.inboxjanitor.com/auth/gmail"
        ... )
        True
    """
    try:
        html_body, text_body = render_email_template(
            "token_refresh_final_failure.html",
            {
                "mailbox_email": mailbox_email,
                "failure_count": failure_count,
                "reconnect_url": reconnect_url,
                "support_email": "support@inboxjanitor.com"
            }
        )

        success = await send_email(
            to=user_email,
            subject="Inbox Janitor: Gmail connection needs attention",
            html_body=html_body,
            text_body=text_body,
            tag='token-refresh-final-failure'
        )

        if success:
            print(f"[OAuth] Token refresh final failure email sent to {user_email} (mailbox: {mailbox_email})")
        else:
            print(f"[OAuth] Failed to send token refresh final failure email to {user_email}")

        return success

    except Exception as e:
        print(f"[OAuth] Error sending token refresh final failure email to {user_email}: {str(e)}")
        return False


async def send_token_refresh_permanent_failure_email(
    user_email: str,
    mailbox_email: str,
    error_reason: str,
    reconnect_url: str
) -> bool:
    """
    Send immediate email for permanent token refresh failure (invalid_grant, token_revoked).

    Args:
        user_email: User's email address
        mailbox_email: Gmail address that was disabled
        error_reason: Error code (invalid_grant, token_revoked, forbidden)
        reconnect_url: Full URL to reconnect Gmail

    Returns:
        True if email sent successfully

    Example:
        >>> await send_token_refresh_permanent_failure_email(
        ...     user_email="user@example.com",
        ...     mailbox_email="work@gmail.com",
        ...     error_reason="invalid_grant",
        ...     reconnect_url="https://app.inboxjanitor.com/auth/gmail"
        ... )
        True
    """
    try:
        html_body, text_body = render_email_template(
            "token_refresh_permanent_failure.html",
            {
                "mailbox_email": mailbox_email,
                "error_reason": error_reason,
                "reconnect_url": reconnect_url
            }
        )

        success = await send_email(
            to=user_email,
            subject="Inbox Janitor: Please reconnect your Gmail account",
            html_body=html_body,
            text_body=text_body,
            tag='token-refresh-permanent-failure'
        )

        if success:
            print(f"[OAuth] Token refresh permanent failure email sent to {user_email} (mailbox: {mailbox_email}, reason: {error_reason})")
        else:
            print(f"[OAuth] Failed to send token refresh permanent failure email to {user_email}")

        return success

    except Exception as e:
        print(f"[OAuth] Error sending token refresh permanent failure email to {user_email}: {str(e)}")
        return False
