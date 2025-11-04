"""
Email metadata extraction utilities.

Functions to extract and parse email metadata from Gmail API responses.

CRITICAL SECURITY:
- NEVER use format='full' or format='raw' with Gmail API
- Only use format='metadata' or format='minimal'
- NO email body content should be extracted or stored
"""

import re
import logging
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from email.utils import parseaddr

logger = logging.getLogger(__name__)


def extract_header(headers: List[Dict], name: str) -> Optional[str]:
    """
    Extract specific header value from Gmail API headers list.

    Gmail API returns headers as list of dicts: [{"name": "From", "value": "..."}]

    Args:
        headers: List of header dicts from Gmail API
        name: Header name to extract (case-insensitive)

    Returns:
        Header value or None if not found

    Usage:
        from_header = extract_header(message['payload']['headers'], 'From')
    """
    if not headers:
        return None

    name_lower = name.lower()

    for header in headers:
        if header.get("name", "").lower() == name_lower:
            return header.get("value")

    return None


def parse_from_header(from_header: str) -> Tuple[str, Optional[str]]:
    """
    Parse From header into email address and display name.

    Handles various formats:
    - "John Doe <john@example.com>" -> ("john@example.com", "John Doe")
    - "john@example.com" -> ("john@example.com", None)
    - "<john@example.com>" -> ("john@example.com", None)

    Args:
        from_header: From header value

    Returns:
        Tuple of (email_address, display_name)

    Usage:
        email, name = parse_from_header("John Doe <john@example.com>")
    """
    if not from_header:
        return ("", None)

    # Use email.utils.parseaddr (handles RFC 2822 format)
    display_name, email_address = parseaddr(from_header)

    # Clean up display name (remove extra quotes, whitespace)
    if display_name:
        display_name = display_name.strip('"\'').strip()
        if not display_name:
            display_name = None

    # Ensure email is lowercase
    email_address = email_address.lower().strip() if email_address else ""

    return (email_address, display_name)


def extract_domain(email: str) -> str:
    """
    Extract domain from email address.

    Args:
        email: Email address

    Returns:
        Domain (lowercase)

    Usage:
        domain = extract_domain("user@example.com")  # "example.com"
    """
    if not email or "@" not in email:
        return ""

    try:
        # Split on @ and take last part
        domain = email.split("@")[-1].lower().strip()
        return domain
    except Exception:
        return ""


def determine_gmail_category(label_ids: List[str]) -> Optional[str]:
    """
    Determine Gmail category from label IDs.

    Gmail assigns category labels like CATEGORY_PROMOTIONS, CATEGORY_SOCIAL, etc.

    Args:
        label_ids: List of Gmail label IDs

    Returns:
        Category name: "promotional", "social", "updates", "forums", "personal", or None

    Usage:
        category = determine_gmail_category(['INBOX', 'CATEGORY_PROMOTIONS'])
        # Returns: "promotional"
    """
    if not label_ids:
        return None

    # Map Gmail category labels to our category names
    category_map = {
        "CATEGORY_PROMOTIONS": "promotional",
        "CATEGORY_SOCIAL": "social",
        "CATEGORY_UPDATES": "updates",
        "CATEGORY_FORUMS": "forums",
        "CATEGORY_PERSONAL": "personal",
    }

    for label_id in label_ids:
        if label_id in category_map:
            return category_map[label_id]

    # If no category label found, assume personal
    return "personal"


def extract_relevant_headers(headers: List[Dict]) -> Dict[str, str]:
    """
    Extract relevant headers for classification.

    Only extracts headers needed for:
    - Classification (List-Unsubscribe, Precedence, etc.)
    - Metadata (From, Subject, Date)
    - NOT full headers (privacy concern)

    Args:
        headers: List of header dicts from Gmail API

    Returns:
        Dict of relevant headers

    Usage:
        relevant = extract_relevant_headers(message['payload']['headers'])
    """
    relevant_header_names = [
        # Classification signals
        "List-Unsubscribe",
        "Precedence",
        "Auto-Submitted",
        "X-Mailer",
        "X-Campaign-ID",
        "X-MC-User",  # Mailchimp
        "X-SG-EID",  # SendGrid
        "X-SFDC-User",  # Salesforce

        # Metadata (not for storage, just for processing)
        "From",
        "Subject",
        "Date",
        "To",
        "Reply-To",
    ]

    result = {}

    for header_name in relevant_header_names:
        value = extract_header(headers, header_name)
        if value:
            result[header_name] = value

    return result


def is_marketing_platform_domain(domain: str) -> bool:
    """
    Check if domain is from a known email marketing platform.

    Marketing platforms indicate bulk/promotional emails.

    Args:
        domain: Email domain

    Returns:
        True if domain is a marketing platform

    Usage:
        is_marketing = is_marketing_platform_domain("sendgrid.net")  # True
    """
    if not domain:
        return False

    domain_lower = domain.lower()

    # Known marketing platform domains and patterns
    marketing_patterns = [
        # Major platforms
        "sendgrid.net",
        "mailgun.org",
        "mailchimp.com",
        "mcsv.net",  # Mailchimp sending domain
        "customeriomail.com",
        "cmail19.com",  # Campaign Monitor
        "cmail20.com",
        "cmail21.com",

        # Generic patterns
        "em.com",
        "email.com",
        "mail.com",
        "bounce",
        "mailer",
        "newsletter",
        "promo",
        "marketing",
    ]

    # Check exact matches
    for pattern in marketing_patterns:
        if pattern in domain_lower:
            return True

    # Check regex patterns
    regex_patterns = [
        r"^em\d+\.",  # em01.example.com, em02.example.com
        r"^mail\d+\.",  # mail1.example.com, mail2.example.com
        r"bounce\.",  # bounce.example.com
        r"\.bounces\.",  # example.bounces.com
    ]

    for pattern in regex_patterns:
        if re.search(pattern, domain_lower):
            return True

    return False


def parse_internal_date(internal_date: str) -> datetime:
    """
    Parse Gmail internalDate (Unix timestamp in milliseconds).

    Args:
        internal_date: Gmail internalDate string (Unix timestamp in ms)

    Returns:
        datetime object

    Usage:
        received_at = parse_internal_date(message['internalDate'])
    """
    try:
        # internalDate is Unix timestamp in milliseconds
        timestamp_ms = int(internal_date)
        timestamp_sec = timestamp_ms / 1000
        return datetime.utcfromtimestamp(timestamp_sec)
    except (ValueError, TypeError):
        # Fallback to current time if parsing fails
        logger.warning(f"Failed to parse internalDate: {internal_date}")
        return datetime.utcnow()


def extract_snippet(snippet: str, max_length: int = 200) -> str:
    """
    Clean and truncate Gmail snippet.

    Gmail provides a snippet (first ~160 chars of body).
    We truncate to 200 chars max for storage.

    Args:
        snippet: Gmail snippet
        max_length: Max length (default 200)

    Returns:
        Cleaned snippet

    Usage:
        clean_snippet = extract_snippet(message['snippet'])
    """
    if not snippet:
        return ""

    # Remove extra whitespace
    snippet = " ".join(snippet.split())

    # Truncate
    if len(snippet) > max_length:
        snippet = snippet[:max_length]

    return snippet


def validate_message_format(message: Dict) -> bool:
    """
    Validate that Gmail API message has expected format.

    Ensures message was fetched with format='metadata' (not 'full' or 'raw').

    Args:
        message: Gmail API message object

    Returns:
        True if valid, False otherwise

    Usage:
        if not validate_message_format(message):
            raise ValueError("Invalid message format")
    """
    # Check required fields
    required_fields = ["id", "threadId", "labelIds", "payload", "internalDate"]

    for field in required_fields:
        if field not in message:
            logger.error(f"Missing required field: {field}")
            return False

    # Check payload has headers
    if "headers" not in message.get("payload", {}):
        logger.error("Missing payload.headers")
        return False

    # CRITICAL SECURITY CHECK: Ensure no body content
    payload = message.get("payload", {})

    # These fields should NOT be present with format='metadata'
    forbidden_fields = ["body", "parts"]

    for field in forbidden_fields:
        if field in payload:
            # Body might be present but should be empty
            if field == "body" and payload[field].get("data"):
                logger.error("SECURITY VIOLATION: Message contains body data!")
                return False

    return True


async def fetch_new_emails_from_history(mailbox_id: str, history_id: str) -> List[str]:
    """
    Fetch new email message IDs from Gmail history (delta sync).

    Uses Gmail's history.list() API for efficient delta sync.
    Only fetches message IDs, not full messages.

    Args:
        mailbox_id: UUID of mailbox
        history_id: Gmail history ID to start from

    Returns:
        List of Gmail message IDs (only INBOX messages)

    Raises:
        Exception: If Gmail API call fails

    Usage:
        message_ids = await fetch_new_emails_from_history(mailbox_id, history_id)
        for msg_id in message_ids:
            metadata = await extract_email_metadata(mailbox_id, msg_id)
    """
    from app.modules.auth.gmail_oauth import get_gmail_service
    from googleapiclient.errors import HttpError

    try:
        # Get authenticated Gmail service
        service = await get_gmail_service(mailbox_id)

        # Fetch history
        all_message_ids = []
        page_token = None

        while True:
            try:
                # Call history.list()
                request_params = {
                    "userId": "me",
                    "startHistoryId": history_id,
                }

                if page_token:
                    request_params["pageToken"] = page_token

                history_response = service.users().history().list(**request_params).execute()

                # Extract message IDs from history
                history = history_response.get("history", [])

                for history_item in history:
                    # Check messagesAdded events
                    messages_added = history_item.get("messagesAdded", [])

                    for msg_added in messages_added:
                        message = msg_added.get("message", {})
                        message_id = message.get("id")
                        label_ids = message.get("labelIds", [])

                        # Only process INBOX messages
                        if message_id and "INBOX" in label_ids:
                            all_message_ids.append(message_id)

                # Check for pagination
                page_token = history_response.get("nextPageToken")

                if not page_token:
                    break

            except HttpError as e:
                if e.resp.status == 404:
                    # History ID not found (too old or invalid)
                    logger.warning(
                        f"History ID {history_id} not found for mailbox {mailbox_id}. "
                        "Full sync may be needed."
                    )
                    # Return empty list - caller should handle full sync
                    return []
                else:
                    raise

        logger.info(
            f"Fetched {len(all_message_ids)} new messages from history for mailbox {mailbox_id}"
        )

        return all_message_ids

    except Exception as e:
        logger.error(
            f"Failed to fetch history for mailbox {mailbox_id}: {e}",
            extra={"mailbox_id": mailbox_id, "history_id": history_id}
        )

        # Log to Sentry
        import sentry_sdk
        sentry_sdk.capture_exception(e, extra={
            "mailbox_id": mailbox_id,
            "history_id": history_id,
            "error": "History fetch failed"
        })

        raise


async def extract_email_metadata(mailbox_id: str, message_id: str):
    """
    Extract email metadata from Gmail API.

    Fetches message using format='metadata' (NO body content).
    Parses headers, labels, and creates EmailMetadata object.

    Args:
        mailbox_id: UUID of mailbox
        message_id: Gmail message ID

    Returns:
        EmailMetadata object

    Raises:
        EmailMetadataExtractError: If extraction fails

    CRITICAL SECURITY: Always uses format='metadata' - never 'full' or 'raw'

    Usage:
        metadata = await extract_email_metadata(mailbox_id, message_id)
        print(f"From: {metadata.from_address}")
    """
    from app.modules.auth.gmail_oauth import get_gmail_service
    from app.models.email_metadata import EmailMetadata, EmailMetadataExtractError
    from googleapiclient.errors import HttpError

    try:
        # Get authenticated Gmail service
        service = await get_gmail_service(mailbox_id)

        # Fetch message with format='metadata'
        # CRITICAL: NEVER use format='full' or format='raw'
        try:
            message = service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",  # Only metadata, NO body
                metadataHeaders=None  # Get all headers (filtered later)
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                raise EmailMetadataExtractError(f"Message {message_id} not found")
            else:
                raise

        # Validate message format (security check)
        if not validate_message_format(message):
            raise EmailMetadataExtractError(
                f"Invalid message format for {message_id} - may contain body data"
            )

        # Extract basic fields
        thread_id = message.get("threadId")
        label_ids = message.get("labelIds", [])
        internal_date = message.get("internalDate")
        snippet = message.get("snippet", "")

        # Extract headers
        payload = message.get("payload", {})
        headers = payload.get("headers", [])

        # Parse From header
        from_header = extract_header(headers, "From")
        if not from_header:
            raise EmailMetadataExtractError(f"Missing From header for message {message_id}")

        from_address, from_name = parse_from_header(from_header)

        if not from_address:
            raise EmailMetadataExtractError(f"Invalid From address for message {message_id}")

        # Extract domain
        from_domain = extract_domain(from_address)

        # Extract subject
        subject = extract_header(headers, "Subject")

        # Determine Gmail category
        gmail_category = determine_gmail_category(label_ids)

        # Extract relevant headers for classification
        relevant_headers = extract_relevant_headers(headers)

        # Parse received date
        received_at = parse_internal_date(internal_date)

        # Clean snippet
        clean_snippet = extract_snippet(snippet)

        # Build EmailMetadata object
        metadata = EmailMetadata(
            message_id=message_id,
            thread_id=thread_id,
            from_address=from_address,
            from_name=from_name,
            from_domain=from_domain,
            subject=subject,
            snippet=clean_snippet,
            gmail_labels=label_ids,
            gmail_category=gmail_category,
            headers=relevant_headers,
            received_at=received_at
        )

        logger.debug(
            f"Extracted metadata for message {message_id}",
            extra={
                "message_id": message_id,
                "from_address": from_address,
                "subject": subject,
                "category": gmail_category
            }
        )

        return metadata

    except EmailMetadataExtractError:
        # Re-raise extraction errors
        raise

    except Exception as e:
        logger.error(
            f"Failed to extract metadata for message {message_id}: {e}",
            extra={
                "mailbox_id": mailbox_id,
                "message_id": message_id,
                "error": str(e)
            }
        )

        # Log to Sentry
        import sentry_sdk
        sentry_sdk.capture_exception(e, extra={
            "mailbox_id": mailbox_id,
            "message_id": message_id,
            "error": "Metadata extraction failed"
        })

        raise EmailMetadataExtractError(
            f"Failed to extract metadata for message {message_id}: {e}"
        )
