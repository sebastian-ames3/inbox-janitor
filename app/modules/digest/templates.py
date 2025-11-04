"""Email template strings for transactional emails.

All templates include both HTML and plain text versions.
HTML templates use inline CSS for maximum email client compatibility.
"""

# ============================================================================
# WELCOME EMAIL (Sent after OAuth connection)
# ============================================================================

WELCOME_EMAIL_SUBJECT = "Welcome to Inbox Janitor! >ù"

WELCOME_EMAIL_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome to Inbox Janitor</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 40px 20px;">
        <tr>
            <td align="center">
                <!-- Main container -->
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 600px;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 40px 40px 20px; text-align: center;">
                            <h1 style="margin: 0; font-size: 32px; color: #111827; font-weight: 700;">
                                >ù Welcome to Inbox Janitor!
                            </h1>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 20px 40px 40px;">
                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Hi there! =K
                            </p>

                            <p style="margin: 0 0 20px; font-size: 16px; line-height: 1.6; color: #374151;">
                                You've successfully connected <strong>{connected_email}</strong> to Inbox Janitor. We're excited to help you keep your inbox clean!
                            </p>

                            <h2 style="margin: 30px 0 15px; font-size: 20px; color: #111827; font-weight: 600;">
                                Here's what happens next:
                            </h2>

                            <ol style="margin: 0 0 30px; padding-left: 20px; font-size: 16px; line-height: 1.8; color: #374151;">
                                <li style="margin-bottom: 12px;">
                                    <strong>We'll analyze your emails</strong> using metadata only (sender, subject, category). We never read your private messages.
                                </li>
                                <li style="margin-bottom: 12px;">
                                    <strong>Promotional emails get moved out of your way</strong> automatically to archive or trash, keeping your inbox focused on real people.
                                </li>
                                <li style="margin-bottom: 12px;">
                                    <strong>You'll get a weekly summary</strong> every Sunday showing what we moved and giving you a chance to undo anything.
                                </li>
                            </ol>

                            <!-- Sandbox mode notice -->
                            <div style="background-color: #fef3c7; border-left: 4px solid: #f59e0b; padding: 16px; margin: 30px 0; border-radius: 4px;">
                                <p style="margin: 0; font-size: 15px; line-height: 1.5; color: #92400e;">
                                    <strong>=á Sandbox Mode Active:</strong> We're currently in <em>review-only mode</em>. No emails will be moved until you enable Action Mode in your settings. This lets you safely review our decisions first!
                                </p>
                            </div>

                            <!-- CTA Button -->
                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 30px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{dashboard_link}" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            Go to Settings Dashboard ’
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 30px 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                                Questions? Just reply to this emailwe'd love to hear from you!
                            </p>

                            <p style="margin: 20px 0 0; font-size: 16px; line-height: 1.6; color: #374151;">
                                Happy cleaning! >ù<br>
                                <span style="color: #6b7280;">The Inbox Janitor Team</span>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 40px; background-color: #f9fafb; border-top: 1px solid #e5e7eb; border-radius: 0 0 8px 8px;">
                            <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #6b7280; text-align: center;">
                                Inbox Janitor " Privacy-first email hygiene<br>
                                <a href="{dashboard_link}" style="color: #2563eb; text-decoration: none;">Settings</a> "
                                <a href="{audit_link}" style="color: #2563eb; text-decoration: none;">Activity Log</a> "
                                <a href="mailto:hello@inboxjanitor.com" style="color: #2563eb; text-decoration: none;">Support</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

WELCOME_EMAIL_TEXT = """Welcome to Inbox Janitor! >ù

Hi there! =K

You've successfully connected {connected_email} to Inbox Janitor. We're excited to help you keep your inbox clean!

Here's what happens next:

1. We'll analyze your emails using metadata only (sender, subject, category). We never read your private messages.

2. Promotional emails get moved out of your way automatically to archive or trash, keeping your inbox focused on real people.

3. You'll get a weekly summary every Sunday showing what we moved and giving you a chance to undo anything.

=á SANDBOX MODE ACTIVE:
We're currently in review-only mode. No emails will be moved until you enable Action Mode in your settings. This lets you safely review our decisions first!

Go to Settings Dashboard: {dashboard_link}

Questions? Just reply to this emailwe'd love to hear from you!

Happy cleaning! >ù
The Inbox Janitor Team

---
Settings: {dashboard_link}
Activity Log: {audit_link}
Support: hello@inboxjanitor.com
"""

# ============================================================================
# WEEKLY DIGEST EMAIL
# ============================================================================

WEEKLY_DIGEST_SUBJECT = "Your Weekly Inbox Summary =Ê"

WEEKLY_DIGEST_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Weekly Digest</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; max-width: 600px;">
                    <!-- Header -->
                    <tr>
                        <td style="padding: 32px 32px 16px;">
                            <h1 style="margin: 0; font-size: 28px; color: #111827; font-weight: 700;">
                                =Ê Your Weekly Summary
                            </h1>
                            <p style="margin: 8px 0 0; font-size: 14px; color: #6b7280;">
                                {period_start} - {period_end}
                            </p>
                        </td>
                    </tr>

                    <!-- Summary Stats -->
                    <tr>
                        <td style="padding: 20px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td style="padding: 16px; background-color: #eff6ff; border-radius: 8px; text-align: center; width: 33%;">
                                        <div style="font-size: 32px; font-weight: 700; color: #2563eb;">{archived_count}</div>
                                        <div style="font-size: 13px; color: #1e40af; margin-top: 4px;">Archived</div>
                                    </td>
                                    <td style="width: 8px;"></td>
                                    <td style="padding: 16px; background-color: #fef2f2; border-radius: 8px; text-align: center; width: 33%;">
                                        <div style="font-size: 32px; font-weight: 700; color: #dc2626;">{trashed_count}</div>
                                        <div style="font-size: 13px; color: #991b1b; margin-top: 4px;">Trashed</div>
                                    </td>
                                    <td style="width: 8px;"></td>
                                    <td style="padding: 16px; background-color: #f0fdf4; border-radius: 8px; text-align: center; width: 33%;">
                                        <div style="font-size: 32px; font-weight: 700; color: #16a34a;">{kept_count}</div>
                                        <div style="font-size: 13px; color: #166534; margin-top: 4px;">Kept</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Review Items (if any) -->
                    {review_items_section}

                    <!-- Top Senders Cleaned -->
                    {top_senders_section}

                    <!-- CTA -->
                    <tr>
                        <td style="padding: 24px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0">
                                <tr>
                                    <td align="center">
                                        <a href="{audit_link}" style="display: inline-block; padding: 12px 28px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 15px; font-weight: 600;">
                                            View Full Activity Log ’
                                        </a>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="padding: 20px 32px; background-color: #f9fafb; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; font-size: 13px; color: #6b7280; text-align: center;">
                                <a href="{dashboard_link}" style="color: #2563eb; text-decoration: none;">Settings</a> "
                                <a href="{audit_link}" style="color: #2563eb; text-decoration: none;">Activity</a> "
                                <a href="mailto:hello@inboxjanitor.com" style="color: #2563eb; text-decoration: none;">Support</a>
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

WEEKLY_DIGEST_TEXT = """Your Weekly Inbox Summary =Ê
{period_start} - {period_end}

SUMMARY:
- Archived: {archived_count} emails
- Trashed: {trashed_count} emails
- Kept: {kept_count} emails

{review_items_section}

{top_senders_section}

View Full Activity Log: {audit_link}

---
Settings: {dashboard_link}
Support: hello@inboxjanitor.com
"""

# ============================================================================
# BACKLOG ANALYSIS EMAIL (One-time cleanup offer)
# ============================================================================

BACKLOG_ANALYSIS_SUBJECT = "Clean up {promotional_count:,} old promotional emails? >ù"

BACKLOG_ANALYSIS_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Backlog Analysis</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f3f4f6;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f3f4f6; padding: 40px 20px;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; max-width: 600px;">
                    <tr>
                        <td style="padding: 32px;">
                            <h1 style="margin: 0 0 16px; font-size: 28px; color: #111827; font-weight: 700;">
                                We found {total_old_emails:,} old emails =ì
                            </h1>

                            <p style="margin: 0 0 24px; font-size: 16px; line-height: 1.6; color: #374151;">
                                Good news! We analyzed your inbox and found <strong>{promotional_count:,} promotional emails</strong> that could be cleaned up automatically.
                            </p>

                            <div style="background-color: #f3f4f6; padding: 20px; border-radius: 8px; margin: 24px 0;">
                                <h3 style="margin: 0 0 12px; font-size: 16px; color: #111827;">What we found:</h3>
                                <ul style="margin: 0; padding-left: 20px; font-size: 15px; line-height: 1.8; color: #374151;">
                                    <li>{promotional_count:,} promotional emails</li>
                                    <li>{social_count:,} social notifications</li>
                                    <li>Estimated {estimated_cleanup_size} MB of storage</li>
                                </ul>
                            </div>

                            <p style="margin: 24px 0; font-size: 16px; line-height: 1.6; color: #374151;">
                                <strong>Would you like us to clean these up for you?</strong><br>
                                <span style="color: #6b7280;">It would take you about {estimated_cleanup_time} minutes to review manually.</span>
                            </p>

                            <table width="100%" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
                                <tr>
                                    <td align="center">
                                        <a href="{cleanup_link}" style="display: inline-block; padding: 14px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 600;">
                                            Yes, Clean Up My Backlog ’
                                        </a>
                                    </td>
                                </tr>
                            </table>

                            <p style="margin: 24px 0 0; font-size: 14px; line-height: 1.5; color: #6b7280; text-align: center;">
                                We'll move these emails to archive or trash (not permanently delete).<br>
                                You can undo any action for 30 days.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""

BACKLOG_ANALYSIS_TEXT = """We found {total_old_emails:,} old emails =ì

Good news! We analyzed your inbox and found {promotional_count:,} promotional emails that could be cleaned up automatically.

WHAT WE FOUND:
- {promotional_count:,} promotional emails
- {social_count:,} social notifications
- Estimated {estimated_cleanup_size} MB of storage

Would you like us to clean these up for you?
(It would take you about {estimated_cleanup_time} minutes to review manually.)

Clean Up My Backlog: {cleanup_link}

We'll move these emails to archive or trash (not permanently delete).
You can undo any action for 30 days.

---
Dashboard: {dashboard_link}
Support: hello@inboxjanitor.com
"""


def format_welcome_email(data: dict) -> tuple[str, str]:
    """
    Format welcome email with user data.

    Args:
        data: Dict with keys: connected_email, dashboard_link, audit_link

    Returns:
        Tuple of (html_body, text_body)
    """
    html_body = WELCOME_EMAIL_HTML.format(**data)
    text_body = WELCOME_EMAIL_TEXT.format(**data)
    return (html_body, text_body)


def format_weekly_digest(data: dict) -> tuple[str, str]:
    """
    Format weekly digest email with summary data.

    Args:
        data: Dict with digest data (see WeeklyDigestData schema)

    Returns:
        Tuple of (html_body, text_body)
    """
    # TODO: Implement review items and top senders sections
    data['review_items_section'] = ''
    data['top_senders_section'] = ''

    html_body = WEEKLY_DIGEST_HTML.format(**data)
    text_body = WEEKLY_DIGEST_TEXT.format(**data)
    return (html_body, text_body)


def format_backlog_analysis(data: dict) -> tuple[str, str]:
    """
    Format backlog analysis email.

    Args:
        data: Dict with backlog data (see BacklogData schema)

    Returns:
        Tuple of (html_body, text_body)
    """
    html_body = BACKLOG_ANALYSIS_HTML.format(**data)
    text_body = BACKLOG_ANALYSIS_TEXT.format(**data)
    return (html_body, text_body)
