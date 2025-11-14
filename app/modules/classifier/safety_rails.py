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

# Negative keywords that DISQUALIFY emails from exception keyword protection
# These indicate marketing emails that should NOT be protected
NEGATIVE_KEYWORDS = [
    "special offer",
    "limited offer",
    "exclusive offer",
    "limited time offer",
    "limited-time offer",
    "flash sale",
    "today only",
    "deal of the day",
    "discount",
    "% off",
    "percent off",
    "sale ends",
]


def check_exception_keywords(metadata: EmailMetadata) -> Optional[SafetyOverride]:
    """
    Check if email contains exception keywords.

    Exception keywords indicate important content that should never be trashed.
    Negative keywords disqualify emails (marketing emails with "special offer", etc.)

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise

    Usage:
        override = check_exception_keywords(metadata)
        if override:
            action = override.new_action

    Example:
        "Job offer for Senior Engineer" -> Protected (exception keyword)
        "Special offer: 50% off" -> NOT protected (negative keyword)
    """
    # Combine subject and snippet for checking
    text_to_check = f"{metadata.subject or ''} {metadata.snippet or ''}".lower()

    # Check negative keywords FIRST (disqualify marketing emails)
    for negative_kw in NEGATIVE_KEYWORDS:
        if negative_kw in text_to_check:
            logger.debug(
                f"Negative keyword '{negative_kw}' found - NOT protecting message {metadata.message_id}",
                extra={
                    "message_id": metadata.message_id,
                    "negative_keyword": negative_kw,
                    "from_address": metadata.from_address
                }
            )
            return None  # Disqualified - do NOT protect

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
    Check if subject is very short AND likely personal (smart detection).

    Short subjects are ONLY flagged if they appear to be personal emails.
    Marketing emails with short subjects ("Sale", "Deal") are NOT flagged.

    Smart Logic:
    - Short subject (<5 chars) + promotional category = NOT flagged (likely marketing)
    - Short subject + all caps (URGENT, HELP, FYI) = flagged (personal urgency)
    - Short subject + personal pronouns (you, I, me) = flagged (personal language)
    - Short subject + common promo words (sale, deal, offer) = NOT flagged (marketing)
    - Short subject + marketing domain = NOT flagged (known sender platform)
    - Default: Flag unknown short subjects as caution (err on side of safety)

    Args:
        metadata: Email metadata

    Returns:
        SafetyOverride if triggered, None otherwise

    Example:
        "Hi" from friend@gmail.com (no category) -> Flagged (personal)
        "Sale" from CATEGORY_PROMOTIONS -> NOT flagged (marketing)
        "URGENT" (all caps) -> Flagged (personal urgency)
        "Free" from sendgrid.net -> NOT flagged (marketing platform)
    """
    if not metadata.subject:
        return None

    subject_clean = metadata.subject.strip()

    # Check if all caps FIRST (personal urgency: "URGENT", "HELP", "FYI")
    # This applies regardless of length
    if subject_clean.isupper() and len(subject_clean) > 1:
        logger.info(
            f"All-caps subject '{subject_clean}' - flagging as potentially important",
            extra={
                "message_id": metadata.message_id,
                "subject": subject_clean,
                "from_address": metadata.from_address
            }
        )
        return SafetyOverride(
            triggered_by="short_subject_allcaps",
            original_action=ClassificationAction.TRASH,
            new_action=ClassificationAction.REVIEW,
            reason=f"All-caps subject '{subject_clean}' - may be personal/urgent"
        )

    # Not short - no other concerns (unless all-caps which was checked above)
    if len(subject_clean) >= 5:
        return None

    # Promotional category + short subject = likely marketing ("Sale", "Deal")
    if metadata.is_promotional:
        logger.debug(
            f"Short subject '{subject_clean}' in promotional category - NOT flagging (likely marketing)",
            extra={
                "message_id": metadata.message_id,
                "subject": subject_clean,
                "from_address": metadata.from_address
            }
        )
        return None

    # Check for personal pronouns (not common in marketing)
    personal_words = ["you", "your", "i", "me", "my", "our", "we"]
    subject_words = subject_clean.lower().split()
    if any(word in subject_words for word in personal_words):
        logger.info(
            f"Short subject '{subject_clean}' contains personal pronouns - flagging",
            extra={
                "message_id": metadata.message_id,
                "subject": subject_clean,
                "from_address": metadata.from_address
            }
        )
        return SafetyOverride(
            triggered_by="short_subject_personal",
            original_action=ClassificationAction.TRASH,
            new_action=ClassificationAction.REVIEW,
            reason=f"Short subject '{subject_clean}' with personal language - may be important"
        )

    # Check if from known marketing domain (don't flag)
    marketing_domains = [
        "sendgrid.net", "mailchimp", "klaviyo", "customeriomail.com",
        "campaignmonitor.com", "mailgun", "amazonses.com", "sparkpostmail.com",
        "email.", "mail.", "newsletter", "marketing"
    ]
    from_domain_lower = metadata.from_domain.lower()
    if any(domain in from_domain_lower for domain in marketing_domains):
        logger.debug(
            f"Short subject '{subject_clean}' from marketing domain '{metadata.from_domain}' - NOT flagging",
            extra={
                "message_id": metadata.message_id,
                "subject": subject_clean,
                "from_domain": metadata.from_domain
            }
        )
        return None

    # Check if subject is common promo word (don't flag)
    promo_words = ["sale", "deal", "offer", "free", "save", "off"]
    if subject_clean.lower() in promo_words:
        logger.debug(
            f"Short subject '{subject_clean}' is common promo word - NOT flagging",
            extra={
                "message_id": metadata.message_id,
                "subject": subject_clean,
                "from_address": metadata.from_address
            }
        )
        return None

    # Default: flag unknown short subjects as caution
    # Better to err on the side of reviewing than trashing
    logger.info(
        f"Short subject '{subject_clean}' with no clear marketing signals - flagging for review",
        extra={
            "message_id": metadata.message_id,
            "subject": subject_clean,
            "from_address": metadata.from_address,
            "gmail_category": metadata.gmail_category
        }
    )
    return SafetyOverride(
        triggered_by="short_subject",
        original_action=ClassificationAction.TRASH,
        new_action=ClassificationAction.REVIEW,
        reason=f"Short subject '{subject_clean}' without clear category - may be personal"
    )


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
        check_short_subject,     # Medium priority: smart short subject detection (re-enabled with improved logic)
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
