"""
Safety rails for email classification.

Safety rails are critical checks that prevent accidentally trashing important emails.
They override the classifier's decision when triggered.

CRITICAL: These are the last line of defense against data loss.
When in doubt, err on the side of keeping emails.
"""

import logging
from typing import Optional

from app.models.email_metadata import EmailMetadata
from app.models.classification import ClassificationAction, SafetyOverride

logger = logging.getLogger(__name__)


# Exception keywords that ALWAYS prevent trashing
# These indicate important/valuable emails that must be kept
EXCEPTION_KEYWORDS = [
    # Financial
    "receipt",
    "invoice",
    "order confirmation",
    "your order",
    "order number",
    "payment",
    "payment confirmation",
    "refund",
    "charge",
    "transaction",
    "statement",
    "bill",
    "tax",
    "w-2",
    "1099",

    # Travel/Reservations
    "booking",
    "reservation",
    "ticket",
    "confirmation",
    "itinerary",
    "boarding pass",

    # Shipping
    "shipped",
    "tracking",
    "delivery",
    "package",

    # Account/Security
    "password",
    "password reset",
    "security alert",
    "security code",
    "verify your",
    "verification code",
    "2fa",
    "two-factor",
    "suspicious login",
    "unusual activity",
    "account suspended",
    "account has been suspended",
    "account locked",
    "reset your password",

    # Important life events
    "medical",
    "health",
    "doctor",
    "appointment",
    "prescription",
    "lab results",
    "insurance",

    # Employment
    "interview",
    "job application",
    "job offer",
    "offer letter",
    "offer of employment",
    "employment offer",
    "resume",
    "hire",
    "hiring",
    "onboard",
    "onboarding",

    # Legal
    "legal",
    "contract",
    "agreement",
    "notice",
    "court",
    "summons",

    # Banking
    "bank",
    "credit card",
    "debit card",
    "loan",
    "mortgage",
    "investment",
]


def check_exception_keywords(metadata: EmailMetadata) -> Optional[SafetyOverride]:
    """
    Check if email contains exception keywords.

    Exception keywords indicate important content that should never be trashed.

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise

    Usage:
        override = check_exception_keywords(metadata)
        if override:
            action = override.new_action
    """
    # Combine subject and snippet for checking
    text_to_check = f"{metadata.subject or ''} {metadata.snippet or ''}".lower()

    # Check for exception keywords
    found_keywords = [kw for kw in EXCEPTION_KEYWORDS if kw in text_to_check]

    if found_keywords:
        logger.info(
            f"Exception keywords triggered for message {metadata.message_id}: {found_keywords[:3]}",
            extra={
                "message_id": metadata.message_id,
                "keywords": found_keywords[:3],
                "from_address": metadata.from_address
            }
        )

        # Determine appropriate action based on keyword type
        # Receipt-type keywords -> ARCHIVE (future value)
        # Security/important keywords -> KEEP (immediate value)
        archive_keywords = ["receipt", "invoice", "order", "booking", "reservation", "shipped", "tracking"]

        if any(kw in found_keywords for kw in archive_keywords):
            new_action = ClassificationAction.ARCHIVE
        else:
            new_action = ClassificationAction.KEEP

        return SafetyOverride(
            triggered_by=f"keyword:{found_keywords[0]}",
            original_action=ClassificationAction.TRASH,  # Would have been trashed
            new_action=new_action,
            reason=f"Contains exception keyword '{found_keywords[0]}' - overriding to {new_action.value}"
        )

    return None


def check_starred(metadata: EmailMetadata) -> Optional[SafetyOverride]:
    """
    Check if email is starred by user.

    Starred emails should always be kept.

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise
    """
    if metadata.is_starred:
        logger.info(
            f"Starred email safety rail triggered for message {metadata.message_id}",
            extra={
                "message_id": metadata.message_id,
                "from_address": metadata.from_address
            }
        )

        return SafetyOverride(
            triggered_by="starred",
            original_action=ClassificationAction.TRASH,
            new_action=ClassificationAction.KEEP,
            reason="User starred this email - keeping regardless of classification"
        )

    return None


def check_important(metadata: EmailMetadata) -> Optional[SafetyOverride]:
    """
    Check if Gmail marked email as important.

    Important emails should always be kept.

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise
    """
    if metadata.is_important:
        logger.info(
            f"Important email safety rail triggered for message {metadata.message_id}",
            extra={
                "message_id": metadata.message_id,
                "from_address": metadata.from_address
            }
        )

        return SafetyOverride(
            triggered_by="important",
            original_action=ClassificationAction.TRASH,
            new_action=ClassificationAction.KEEP,
            reason="Gmail marked as important - keeping regardless of classification"
        )

    return None


def check_recent_thread(metadata: EmailMetadata) -> Optional[SafetyOverride]:
    """
    Check if email is very recent (within 3 days).

    Recent emails should be reviewed, not auto-trashed (in case of false positive).

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise
    """
    from datetime import datetime, timedelta

    three_days_ago = datetime.utcnow() - timedelta(days=3)

    if metadata.received_at > three_days_ago:
        # Recent email - demote TRASH to REVIEW (let user review first)
        return SafetyOverride(
            triggered_by="recent",
            original_action=ClassificationAction.TRASH,
            new_action=ClassificationAction.REVIEW,
            reason="Email received within 3 days - needs review before trashing"
        )

    return None


def check_short_subject(metadata: EmailMetadata) -> Optional[SafetyOverride]:
    """
    Check if subject is very short (may be personal/important).

    Short subjects like "Hi" or "Question" are often personal emails.

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise
    """
    if not metadata.subject:
        return None

    # If subject is 1-2 words and no promotional signals, be cautious
    words = metadata.subject.split()

    if len(words) <= 2 and not metadata.is_promotional:
        return SafetyOverride(
            triggered_by="short_subject",
            original_action=ClassificationAction.TRASH,
            new_action=ClassificationAction.REVIEW,
            reason="Very short subject without promotional category - may be personal"
        )

    return None


def apply_safety_rails(metadata: EmailMetadata, proposed_action: ClassificationAction) -> tuple[ClassificationAction, Optional[SafetyOverride]]:
    """
    Apply all safety rails to proposed action.

    Safety rails can override the classifier's decision to prevent data loss.

    Args:
        metadata: Email metadata
        proposed_action: Action proposed by classifier

    Returns:
        Tuple of (final_action, override_info)
        - If no override: (proposed_action, None)
        - If overridden: (new_action, SafetyOverride)

    Usage:
        final_action, override = apply_safety_rails(metadata, ClassificationAction.TRASH)
        if override:
            logger.warning(f"Action overridden: {override.reason}")
    """
    # Only apply safety rails if proposed action is TRASH
    # (No need to override KEEP, ARCHIVE, or REVIEW)
    if proposed_action != ClassificationAction.TRASH:
        return (proposed_action, None)

    # Check each safety rail in priority order
    safety_checks = [
        check_starred,           # Highest priority: user explicitly starred
        check_important,         # High priority: Gmail marked important
        check_exception_keywords, # High priority: contains critical keywords
        check_recent_thread,     # Medium priority: recent email (3 days)
        # check_short_subject is disabled for now (too many false positives)
    ]

    for check_func in safety_checks:
        override = check_func(metadata)
        if override:
            logger.warning(
                f"Safety rail triggered: {override.triggered_by} for message {metadata.message_id}",
                extra={
                    "message_id": metadata.message_id,
                    "from_address": metadata.from_address,
                    "trigger": override.triggered_by,
                    "original_action": override.original_action.value,
                    "new_action": override.new_action.value
                }
            )
            return (override.new_action, override)

    # No safety rails triggered
    return (proposed_action, None)


def add_exception_keyword(keyword: str) -> None:
    """
    Add a new exception keyword at runtime.

    Useful for user-specific keywords or learning from mistakes.

    Args:
        keyword: Keyword to add (lowercase)

    Usage:
        add_exception_keyword("lawsuit")
    """
    keyword_lower = keyword.lower().strip()

    if keyword_lower and keyword_lower not in EXCEPTION_KEYWORDS:
        EXCEPTION_KEYWORDS.append(keyword_lower)
        logger.info(f"Added exception keyword: {keyword_lower}")


def get_exception_keywords() -> list[str]:
    """
    Get list of all exception keywords.

    Returns:
        List of exception keywords

    Usage:
        keywords = get_exception_keywords()
        print(f"Protecting {len(keywords)} keyword patterns")
    """
    return EXCEPTION_KEYWORDS.copy()
