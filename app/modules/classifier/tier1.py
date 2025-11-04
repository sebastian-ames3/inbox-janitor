"""
Tier 1 (metadata-based) email classifier.

The main classification engine that uses metadata signals to determine
email importance and recommend actions.

Accuracy target: 80%+ (without AI)
"""

import logging
from typing import Tuple

from app.models.email_metadata import EmailMetadata
from app.models.classification import (
    ClassificationResult,
    ClassificationAction,
    ClassificationMetadata,
    ClassificationTier
)
from app.modules.classifier.signals import calculate_all_signals
from app.modules.classifier.safety_rails import apply_safety_rails

logger = logging.getLogger(__name__)


# Classification thresholds
THRESHOLD_AUTO_TRASH = 0.85  # Auto-trash if confidence >= 0.85
THRESHOLD_ARCHIVE = 0.55     # Archive if confidence >= 0.55
THRESHOLD_REVIEW = 0.30      # Review if confidence >= 0.30
# Below 0.30 = KEEP


def classify_email_tier1(metadata: EmailMetadata) -> ClassificationResult:
    """
    Classify email using Tier 1 (metadata-based) signals.

    Process:
    1. Calculate all signals (Gmail category, headers, domain, subject)
    2. Aggregate confidence scores
    3. Determine action based on thresholds
    4. Apply safety rails (exception keywords, starred, etc.)
    5. Build classification result

    Args:
        metadata: Email metadata

    Returns:
        ClassificationResult with action, confidence, signals, and reason

    Thresholds:
    - ≥0.85: TRASH (high confidence spam/promotional)
    - 0.55-0.84: ARCHIVE (promotional but may have value)
    - 0.30-0.54: REVIEW (uncertain)
    - <0.30: KEEP (likely important)

    Usage:
        result = classify_email_tier1(metadata)
        if result.should_take_action:
            # Take action automatically
            execute_action(result.action)
        else:
            # Send to review
            send_to_digest(result)
    """
    import time
    start_time = time.time()

    logger.debug(
        f"Classifying email {metadata.message_id} from {metadata.from_address}",
        extra={
            "message_id": metadata.message_id,
            "from_address": metadata.from_address,
            "subject": metadata.subject
        }
    )

    # Calculate all signals
    signals = calculate_all_signals(metadata)

    # Aggregate confidence score
    total_score = sum(signal.score for signal in signals)

    # Normalize score to 0.0-1.0 range
    # Maximum possible score is ~2.5 (if all positive signals max out)
    # Minimum is ~-2.3 (if all negative signals max out)
    # Map this to 0.0-1.0 where:
    # - Negative scores -> low confidence (0.0-0.3) = KEEP
    # - Zero -> medium confidence (0.4-0.6) = REVIEW
    # - Positive scores -> high confidence (0.6-1.0) = TRASH/ARCHIVE

    # Simple normalization: scale from -2.0 to +2.0 range to 0.0-1.0
    # confidence = (total_score + 2.0) / 4.0
    # But let's use a more intuitive approach:

    if total_score >= 1.5:
        confidence = 0.95  # Very high confidence trash
    elif total_score >= 1.0:
        confidence = 0.85  # High confidence trash
    elif total_score >= 0.7:
        confidence = 0.70  # Moderate-high confidence
    elif total_score >= 0.5:
        confidence = 0.60  # Moderate confidence
    elif total_score >= 0.3:
        confidence = 0.50  # Low-moderate confidence
    elif total_score >= 0.0:
        confidence = 0.40  # Low confidence
    elif total_score >= -0.3:
        confidence = 0.30  # Very low confidence
    elif total_score >= -0.5:
        confidence = 0.20  # Keep signal
    else:
        confidence = 0.10  # Strong keep signal

    # Determine action based on confidence thresholds
    if confidence >= THRESHOLD_AUTO_TRASH:
        action = ClassificationAction.TRASH
    elif confidence >= THRESHOLD_ARCHIVE:
        action = ClassificationAction.ARCHIVE
    elif confidence >= THRESHOLD_REVIEW:
        action = ClassificationAction.REVIEW
    else:
        action = ClassificationAction.KEEP

    # Build human-readable reason
    reason = build_reason(action, confidence, signals, metadata)

    # Apply safety rails (may override action)
    final_action, override = apply_safety_rails(metadata, action)

    overridden = override is not None
    override_reason = override.reason if override else None

    if overridden:
        # Update reason to include override
        reason = f"{reason} | OVERRIDDEN: {override_reason}"

    # Calculate processing time
    processing_time_ms = (time.time() - start_time) * 1000

    # Build classification result
    result = ClassificationResult(
        action=final_action,
        confidence=confidence,
        signals=signals,
        reason=reason,
        overridden=overridden,
        override_reason=override_reason
    )

    logger.info(
        f"Classified {metadata.message_id}: {final_action.value} "
        f"(confidence={confidence:.2f}, overridden={overridden})",
        extra={
            "message_id": metadata.message_id,
            "from_address": metadata.from_address,
            "action": final_action.value,
            "confidence": confidence,
            "overridden": overridden,
            "processing_time_ms": processing_time_ms
        }
    )

    return result


def build_reason(
    action: ClassificationAction,
    confidence: float,
    signals: list,
    metadata: EmailMetadata
) -> str:
    """
    Build human-readable explanation for classification.

    Args:
        action: Recommended action
        confidence: Confidence score
        signals: List of classification signals
        metadata: Email metadata

    Returns:
        Human-readable reason string

    Example:
        "Promotional email from marketing platform with unsubscribe link (confidence: 0.95)"
    """
    # Get top contributing signals (score != 0)
    contributing_signals = [s for s in signals if s.score != 0]

    # Sort by absolute score (most impactful first)
    contributing_signals.sort(key=lambda s: abs(s.score), reverse=True)

    # Build reason from top signals
    if action == ClassificationAction.TRASH:
        reason_parts = ["Promotional email"]

        # Add top signal reasons
        for signal in contributing_signals[:3]:
            if signal.score > 0:  # Positive signals (trash indicators)
                if signal.name == "gmail_category" and signal.score >= 0.5:
                    reason_parts.append("in promotional/social category")
                elif signal.name == "list_unsubscribe":
                    reason_parts.append("with unsubscribe link")
                elif signal.name == "sender_domain":
                    reason_parts.append("from marketing platform")
                elif signal.name == "subject_patterns":
                    reason_parts.append("with promotional subject")

        reason = " ".join(reason_parts)

    elif action == ClassificationAction.ARCHIVE:
        reason = "Promotional/transactional email with possible future value"

        # Check if it's receipt-like
        if any(s.name == "receipt_indicators" and s.score < 0 for s in contributing_signals):
            reason = "Transactional email (receipt/booking/order confirmation)"

    elif action == ClassificationAction.REVIEW:
        reason = "Uncertain classification - needs human review"

        # Add context
        if confidence >= 0.45:
            reason += " (moderate promotional signals)"
        else:
            reason += " (mixed signals)"

    else:  # KEEP
        reason = "Important email"

        # Check for keep signals
        if any(s.name == "starred_or_important" and s.score < 0 for s in contributing_signals):
            reason = "User-important email (starred or marked important)"
        elif metadata.is_personal:
            reason = "Personal email (not promotional)"
        elif confidence < 0.2:
            reason = "Important email (strong keep signals)"

    # Add confidence
    reason += f" (confidence: {confidence:.2f})"

    return reason


def get_classification_metadata(processing_time_ms: float) -> ClassificationMetadata:
    """
    Build classification metadata for logging.

    Args:
        processing_time_ms: Time taken to classify (milliseconds)

    Returns:
        ClassificationMetadata object

    Usage:
        metadata = get_classification_metadata(processing_time_ms)
    """
    return ClassificationMetadata(
        tier=ClassificationTier.TIER_1,
        processing_time_ms=processing_time_ms,
        model_used=None,  # No AI model for Tier 1
        cost=None,  # No cost for Tier 1
        version="1.0"
    )


def explain_classification(result: ClassificationResult, metadata: EmailMetadata) -> str:
    """
    Generate detailed explanation of classification for debugging/learning.

    Args:
        result: Classification result
        metadata: Email metadata

    Returns:
        Multi-line explanation string

    Usage:
        explanation = explain_classification(result, metadata)
        print(explanation)
    """
    lines = [
        f"=== Classification Explanation ===",
        f"Message ID: {metadata.message_id}",
        f"From: {metadata.from_address}",
        f"Subject: {metadata.subject}",
        f"",
        f"Action: {result.action.value.upper()}",
        f"Confidence: {result.confidence:.2f}",
        f"",
        f"Signals:",
    ]

    # Add each signal
    for signal in result.signals:
        if signal.score != 0:
            direction = "→ TRASH" if signal.score > 0 else "→ KEEP"
            lines.append(f"  [{signal.score:+.2f}] {signal.name}: {signal.reason} {direction}")

    # Add total
    total_score = result.total_signal_score
    lines.append(f"")
    lines.append(f"Total Score: {total_score:+.2f}")

    # Add override if present
    if result.overridden:
        lines.append(f"")
        lines.append(f"SAFETY OVERRIDE: {result.override_reason}")

    # Add reason
    lines.append(f"")
    lines.append(f"Reason: {result.reason}")

    return "\n".join(lines)
