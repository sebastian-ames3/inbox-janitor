"""
Individual classification signals for Tier 1 (metadata-based) classifier.

Each signal function analyzes one aspect of email metadata and returns a score.
Scores are aggregated to determine the final classification.

Signal scoring:
- Positive scores (0.0 to 1.0) indicate spam/promotional (trash/archive)
- Negative scores (-1.0 to 0.0) indicate important (keep)
- Zero means neutral/no signal
"""

import logging
from typing import Optional

from app.models.email_metadata import EmailMetadata
from app.models.classification import ClassificationSignal
from app.modules.ingest.metadata_extractor import is_marketing_platform_domain

logger = logging.getLogger(__name__)


def signal_gmail_category(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on Gmail's automatic category.

    Gmail categories are highly accurate for promotional content.

    Scoring (tuned based on 18K+ email analysis):
    - CATEGORY_PROMOTIONS: +0.70 (very strong trash signal)
    - CATEGORY_SOCIAL: +0.60 (strong trash signal)
    - CATEGORY_UPDATES: +0.40 (moderate archive signal)
    - CATEGORY_FORUMS: +0.30 (light archive signal)
    - CATEGORY_PERSONAL: -0.40 (strong keep signal)
    - No category: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    score = 0.0
    reason = "No Gmail category"

    if metadata.is_promotional:
        score = 0.70  # Increased from 0.60 to push more emails to TRASH
        reason = "Gmail categorized as CATEGORY_PROMOTIONS"
    elif metadata.is_social:
        score = 0.60  # Increased from 0.50
        reason = "Gmail categorized as CATEGORY_SOCIAL"
    elif metadata.is_updates:
        score = 0.40  # Increased from 0.30
        reason = "Gmail categorized as CATEGORY_UPDATES"
    elif metadata.is_forums:
        score = 0.30  # Increased from 0.20
        reason = "Gmail categorized as CATEGORY_FORUMS"
    elif metadata.is_personal:
        score = -0.40  # Increased negative from -0.30
        reason = "Gmail categorized as CATEGORY_PERSONAL"

    return ClassificationSignal(
        name="gmail_category",
        score=score,
        reason=reason
    )


def signal_list_unsubscribe(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on List-Unsubscribe header.

    This header is a legal requirement for commercial email in many jurisdictions.
    Its presence strongly indicates marketing/promotional content.

    Scoring:
    - Has List-Unsubscribe: +0.40 (strong trash signal)
    - No List-Unsubscribe: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    if metadata.has_unsubscribe_header:
        return ClassificationSignal(
            name="list_unsubscribe",
            score=0.40,
            reason="Has List-Unsubscribe header (commercial email)"
        )
    else:
        return ClassificationSignal(
            name="list_unsubscribe",
            score=0.0,
            reason="No List-Unsubscribe header"
        )


def signal_bulk_headers(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on bulk mail headers.

    Checks for:
    - Precedence: bulk
    - Auto-Submitted: auto-generated

    Scoring:
    - Both headers: +0.50 (strong trash signal)
    - Precedence: bulk only: +0.35 (moderate trash signal)
    - Auto-Submitted only: +0.30 (light archive signal)
    - Neither: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    has_bulk = metadata.get_header("Precedence") == "bulk"
    has_auto_submitted = metadata.get_header("Auto-Submitted") == "auto-generated"

    if has_bulk and has_auto_submitted:
        return ClassificationSignal(
            name="bulk_headers",
            score=0.50,
            reason="Has both Precedence:bulk and Auto-Submitted headers"
        )
    elif has_bulk:
        return ClassificationSignal(
            name="bulk_headers",
            score=0.35,
            reason="Has Precedence:bulk header"
        )
    elif has_auto_submitted:
        return ClassificationSignal(
            name="bulk_headers",
            score=0.30,
            reason="Has Auto-Submitted:auto-generated header"
        )
    else:
        return ClassificationSignal(
            name="bulk_headers",
            score=0.0,
            reason="No bulk mail headers"
        )


def signal_sender_domain(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on sender domain analysis.

    Checks if sender domain is from a known email marketing platform.

    Scoring:
    - Marketing platform domain: +0.45 (strong trash signal)
    - Normal domain: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    if is_marketing_platform_domain(metadata.from_domain):
        return ClassificationSignal(
            name="sender_domain",
            score=0.45,
            reason=f"Marketing platform domain: {metadata.from_domain}"
        )
    else:
        return ClassificationSignal(
            name="sender_domain",
            score=0.0,
            reason=f"Normal domain: {metadata.from_domain}"
        )


def signal_subject_patterns(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on subject line patterns.

    Checks for common promotional patterns:
    - Percentage off (50% off, 20% off, etc.)
    - Limited time offers
    - All caps subjects
    - Excessive punctuation (!!!)
    - Emoji usage

    Scoring:
    - Multiple patterns: +0.35 (moderate trash signal)
    - One pattern: +0.20 (light trash signal)
    - No patterns: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    if not metadata.subject:
        return ClassificationSignal(
            name="subject_patterns",
            score=0.0,
            reason="No subject"
        )

    subject_lower = metadata.subject.lower()
    patterns_found = []

    # Check for percentage off
    import re
    if re.search(r'\d+%\s*off', subject_lower):
        patterns_found.append("percentage off")

    # Check for limited time
    limited_time_keywords = ["limited time", "today only", "hurry", "expires", "last chance", "don't miss"]
    if any(keyword in subject_lower for keyword in limited_time_keywords):
        patterns_found.append("urgency language")

    # Check for all caps (more than 50% caps)
    if metadata.subject and len(metadata.subject) > 5:
        caps_ratio = sum(1 for c in metadata.subject if c.isupper()) / len(metadata.subject)
        if caps_ratio > 0.5:
            patterns_found.append("excessive caps")

    # Check for excessive punctuation
    if re.search(r'[!?]{2,}', metadata.subject):
        patterns_found.append("excessive punctuation")

    # Check for emoji (basic check for common emoji unicode ranges)
    if re.search(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]', metadata.subject):
        patterns_found.append("emoji")

    if len(patterns_found) >= 2:
        score = 0.35
        reason = f"Multiple promotional patterns: {', '.join(patterns_found)}"
    elif len(patterns_found) == 1:
        score = 0.20
        reason = f"Promotional pattern: {patterns_found[0]}"
    else:
        score = 0.0
        reason = "No promotional patterns in subject"

    return ClassificationSignal(
        name="subject_patterns",
        score=score,
        reason=reason
    )


def signal_starred_or_important(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on user-applied labels.

    If user starred or marked as important, strongly prefer keeping.

    Scoring:
    - Starred or Important: -0.80 (very strong keep signal)
    - Neither: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    if metadata.is_starred:
        return ClassificationSignal(
            name="starred_or_important",
            score=-0.80,
            reason="User starred this email"
        )
    elif metadata.is_important:
        return ClassificationSignal(
            name="starred_or_important",
            score=-0.80,
            reason="Gmail marked as important"
        )
    else:
        return ClassificationSignal(
            name="starred_or_important",
            score=0.0,
            reason="Not starred or important"
        )


def signal_receipt_indicators(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal based on receipt/transactional indicators.

    Checks subject and snippet for receipt-related keywords.
    These should be archived, not trashed (future value).

    Scoring:
    - Receipt keywords found: -0.40 (moderate keep/archive signal)
    - No receipt keywords: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    receipt_keywords = [
        "receipt", "invoice", "order confirmation", "payment",
        "booking confirmation", "reservation", "ticket",
        "shipped", "tracking", "delivery"
    ]

    text_to_check = f"{metadata.subject or ''} {metadata.snippet or ''}".lower()

    found_keywords = [kw for kw in receipt_keywords if kw in text_to_check]

    if found_keywords:
        return ClassificationSignal(
            name="receipt_indicators",
            score=-0.40,
            reason=f"Receipt keywords found: {', '.join(found_keywords[:2])}"
        )
    else:
        return ClassificationSignal(
            name="receipt_indicators",
            score=0.0,
            reason="No receipt indicators"
        )


def signal_automated_monitoring(metadata: EmailMetadata) -> ClassificationSignal:
    """
    Signal for automated monitoring/deployment emails.

    Detects automated notifications from deployment services, monitoring tools,
    CI/CD platforms, etc. These are typically safe to archive or trash.

    Scoring:
    - Automated monitoring keywords + automated sender: +0.50 (strong archive signal)
    - Automated monitoring keywords only: +0.30 (moderate archive signal)
    - Neither: 0.0 (neutral)

    Args:
        metadata: Email metadata

    Returns:
        ClassificationSignal
    """
    # Automated sender domains
    automated_domains = [
        'railway.app', 'vercel.com', 'netlify.app', 'heroku.com',
        'github.com', 'gitlab.com', 'circleci.com', 'travis-ci.org',
        'sentry.io', 'datadog.com', 'newrelic.com', 'pagerduty.com',
        'statuspage.io', 'uptimerobot.com'
    ]

    # Automated subject keywords
    automated_keywords = [
        'deployment', 'deploy', 'build failed', 'build succeeded',
        'crash', 'error report', 'exception', 'alert',
        'monitoring', 'uptime', 'downtime', 'incident',
        'ci/cd', 'pipeline', 'workflow', '[github]', '[gitlab]'
    ]

    is_automated_domain = any(domain in metadata.from_domain.lower() for domain in automated_domains)

    subject_lower = (metadata.subject or '').lower()
    has_automated_keywords = any(keyword in subject_lower for keyword in automated_keywords)

    if is_automated_domain and has_automated_keywords:
        return ClassificationSignal(
            name="automated_monitoring",
            score=0.50,
            reason=f"Automated monitoring email from {metadata.from_domain}"
        )
    elif has_automated_keywords:
        return ClassificationSignal(
            name="automated_monitoring",
            score=0.30,
            reason="Automated monitoring keywords in subject"
        )
    else:
        return ClassificationSignal(
            name="automated_monitoring",
            score=0.0,
            reason="Not automated monitoring email"
        )


def calculate_all_signals(metadata: EmailMetadata) -> list[ClassificationSignal]:
    """
    Calculate all classification signals for an email.

    Runs all signal functions and returns list of signals.

    Args:
        metadata: Email metadata

    Returns:
        List of ClassificationSignal objects

    Usage:
        signals = calculate_all_signals(metadata)
        total_score = sum(s.score for s in signals)
    """
    signals = [
        signal_gmail_category(metadata),
        signal_list_unsubscribe(metadata),
        signal_bulk_headers(metadata),
        signal_sender_domain(metadata),
        signal_subject_patterns(metadata),
        signal_starred_or_important(metadata),
        signal_receipt_indicators(metadata),
        signal_automated_monitoring(metadata),  # NEW: Catch Railway/GitHub/etc.
    ]

    # Filter out neutral signals (score == 0) for cleaner logging
    # Actually, keep all signals for transparency
    return signals
