"""
Tier 2 (AI-based) email classifier.

Uses OpenAI GPT-4o-mini for uncertain emails where Tier 1 confidence is low.
Includes Redis caching to reduce API costs.

Cost optimization:
- Only called if Tier 1 confidence < 0.90
- Target: ~30% of emails use AI
- Cache AI responses for 30 days (same sender domain + subject pattern)
- Expected cost: ~$0.003 per uncached classification

Accuracy target: 95%+ (combined with Tier 1)
"""

import logging
import hashlib
import json
from datetime import timedelta
from typing import Optional, Dict

from app.models.email_metadata import EmailMetadata
from app.models.classification import (
    ClassificationResult,
    ClassificationAction,
    ClassificationSignal,
    ClassificationMetadata,
    ClassificationTier
)
from app.modules.classifier.openai_client import OpenAIClassifier
from app.modules.classifier.safety_rails import apply_safety_rails
from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis cache prefix
CACHE_KEY_PREFIX = "ai_classification"


def get_cache_key(metadata: EmailMetadata) -> str:
    """
    Generate cache key for AI classification.

    Cache key is based on:
    - Sender domain (not full address, for privacy)
    - Subject pattern (first 50 chars, lowercased, trimmed)

    This allows caching for similar emails from same sender.

    Args:
        metadata: Email metadata

    Returns:
        Cache key string

    Example:
        "ai_classification:abc123:def456"
    """
    # Use sender domain (not full email)
    sender_domain = metadata.from_domain

    # Use subject pattern (first 50 chars, normalized)
    subject_pattern = (metadata.subject or "")[:50].lower().strip()

    # Hash the pattern for shorter keys
    subject_hash = hashlib.md5(subject_pattern.encode()).hexdigest()[:8]

    # Combine
    cache_key = f"{CACHE_KEY_PREFIX}:{sender_domain}:{subject_hash}"

    return cache_key


async def get_cached_classification(cache_key: str) -> Optional[Dict]:
    """
    Get cached AI classification from Redis.

    Args:
        cache_key: Cache key

    Returns:
        Cached result dict or None if not found

    Usage:
        cached = await get_cached_classification(cache_key)
        if cached:
            return cached
    """
    try:
        import redis.asyncio as redis

        # Get Redis connection
        redis_client = redis.from_url(settings.REDIS_URL)

        # Get cached value
        cached_value = await redis_client.get(cache_key)

        await redis_client.close()

        if cached_value:
            # Parse JSON
            cached_dict = json.loads(cached_value)

            logger.info(
                f"AI classification cache HIT for key {cache_key}",
                extra={"cache_key": cache_key}
            )

            return cached_dict

        logger.debug(
            f"AI classification cache MISS for key {cache_key}",
            extra={"cache_key": cache_key}
        )

        return None

    except Exception as e:
        logger.warning(
            f"Failed to get cached AI classification: {e}",
            extra={"cache_key": cache_key, "error": str(e)}
        )
        return None


async def set_cached_classification(cache_key: str, result: Dict, ttl_days: int = 30):
    """
    Cache AI classification result in Redis.

    Args:
        cache_key: Cache key
        result: Classification result dict
        ttl_days: Time-to-live in days (default 30)

    Usage:
        await set_cached_classification(cache_key, result)
    """
    try:
        import redis.asyncio as redis

        # Get Redis connection
        redis_client = redis.from_url(settings.REDIS_URL)

        # Serialize result
        result_json = json.dumps(result)

        # Set with TTL
        ttl_seconds = ttl_days * 24 * 60 * 60
        await redis_client.setex(cache_key, ttl_seconds, result_json)

        await redis_client.close()

        logger.debug(
            f"Cached AI classification for key {cache_key} (TTL: {ttl_days} days)",
            extra={"cache_key": cache_key}
        )

    except Exception as e:
        logger.warning(
            f"Failed to cache AI classification: {e}",
            extra={"cache_key": cache_key, "error": str(e)}
        )


async def classify_email_tier2(metadata: EmailMetadata) -> ClassificationResult:
    """
    Classify email using Tier 2 (AI-based) classifier.

    Process:
    1. Check Redis cache for similar email classification
    2. If cache hit, return cached result
    3. If cache miss, call OpenAI API
    4. Reduce confidence by 0.1 for safety (AI less certain than metadata)
    5. Apply safety rails
    6. Cache result for 30 days
    7. Return ClassificationResult

    Args:
        metadata: Email metadata

    Returns:
        ClassificationResult with action, confidence, signals, and reason

    Usage:
        result = await classify_email_tier2(metadata)
        if result.confidence >= 0.85:
            # High confidence, take action
            execute_action(result.action)
    """
    import time
    start_time = time.time()

    logger.debug(
        f"AI classifying email {metadata.message_id} from {metadata.from_address}",
        extra={
            "message_id": metadata.message_id,
            "from_address": metadata.from_address,
            "subject": metadata.subject
        }
    )

    # Generate cache key
    cache_key = get_cache_key(metadata)

    # Check cache
    cached_result = await get_cached_classification(cache_key)

    if cached_result:
        # Use cached result
        action = ClassificationAction(cached_result["action"])
        confidence = cached_result["confidence"]
        reason = cached_result["reason"]
        tokens_used = 0  # No API call
        cost = 0.0
        from_cache = True
    else:
        # Call OpenAI API
        classifier = OpenAIClassifier()
        ai_result = await classifier.classify_email(metadata)

        # Check for errors
        if "error" in ai_result:
            # AI call failed, return conservative KEEP
            logger.warning(
                f"AI classification failed for {metadata.message_id}: {ai_result['error']}",
                extra={"message_id": metadata.message_id}
            )

            # Return conservative KEEP result
            return ClassificationResult(
                action=ClassificationAction.KEEP,
                confidence=0.0,
                signals=[
                    ClassificationSignal(
                        name="ai_error",
                        score=-1.0,
                        reason=f"AI failed: {ai_result.get('reason', 'Unknown error')}"
                    )
                ],
                reason=f"AI classification failed, keeping for safety: {ai_result['reason']}",
                overridden=False,
                override_reason=None
            )

        # Extract AI response
        action = ClassificationAction(ai_result["action"])
        confidence = ai_result["confidence"]
        reason = ai_result["reason"]
        tokens_used = ai_result["tokens_used"]
        cost = ai_result["cost"]
        from_cache = False

        # Cache result for future use
        await set_cached_classification(
            cache_key,
            {
                "action": action.value,
                "confidence": confidence,
                "reason": reason
            },
            ttl_days=settings.AI_CACHE_TTL_DAYS
        )

    # Reduce confidence by 0.1 for safety (AI less certain than metadata)
    # This prevents over-reliance on AI
    adjusted_confidence = max(0.0, confidence - 0.1)

    logger.debug(
        f"AI confidence adjustment: {confidence:.2f} → {adjusted_confidence:.2f}",
        extra={
            "message_id": metadata.message_id,
            "original": confidence,
            "adjusted": adjusted_confidence
        }
    )

    # Create signal representing AI classification
    ai_signal = ClassificationSignal(
        name="ai_classification",
        score=1.0 if action == ClassificationAction.TRASH else -1.0,
        reason=f"AI classified as {action.value}: {reason}"
    )

    # Apply safety rails (may override action)
    final_action, override = apply_safety_rails(metadata, action)

    overridden = override is not None
    override_reason = override.reason if override else None

    if overridden:
        reason = f"{reason} | OVERRIDDEN: {override_reason}"

    # Calculate processing time
    processing_time_ms = (time.time() - start_time) * 1000

    # Build classification result
    result = ClassificationResult(
        action=final_action,
        confidence=adjusted_confidence,
        signals=[ai_signal],
        reason=reason,
        overridden=overridden,
        override_reason=override_reason
    )

    logger.info(
        f"AI classified {metadata.message_id}: {final_action.value} "
        f"(confidence={adjusted_confidence:.2f}, from_cache={from_cache}, cost=${cost:.4f})",
        extra={
            "message_id": metadata.message_id,
            "from_address": metadata.from_address,
            "action": final_action.value,
            "confidence": adjusted_confidence,
            "overridden": overridden,
            "from_cache": from_cache,
            "tokens": tokens_used,
            "cost": cost,
            "processing_time_ms": processing_time_ms
        }
    )

    return result


def combine_tier1_tier2_results(
    tier1_result: ClassificationResult,
    tier2_result: ClassificationResult
) -> ClassificationResult:
    """
    Combine Tier 1 (metadata) and Tier 2 (AI) classification results.

    Weighted average:
    - Tier 1: 40% weight (metadata signals are reliable)
    - Tier 2: 60% weight (AI has broader context)

    Args:
        tier1_result: Tier 1 classification result
        tier2_result: Tier 2 classification result

    Returns:
        Combined ClassificationResult

    Usage:
        combined = combine_tier1_tier2_results(tier1, tier2)
    """
    # Calculate weighted confidence
    combined_confidence = (tier1_result.confidence * 0.4) + (tier2_result.confidence * 0.6)

    # Use AI action if confidence difference is significant
    if abs(tier2_result.confidence - tier1_result.confidence) > 0.2:
        # AI is much more confident, use AI action
        final_action = tier2_result.action
        reason = f"AI override: {tier2_result.reason} (Tier 1: {tier1_result.reason})"
    elif tier2_result.action == tier1_result.action:
        # Agreement, use same action
        final_action = tier1_result.action
        reason = f"Tier 1 + AI agree: {tier2_result.reason}"
    else:
        # Disagreement, be conservative (choose safer action)
        if ClassificationAction.KEEP in [tier1_result.action, tier2_result.action]:
            final_action = ClassificationAction.KEEP
            reason = f"Tier 1 and AI disagree, keeping for safety (Tier 1: {tier1_result.action.value}, AI: {tier2_result.action.value})"
        elif ClassificationAction.REVIEW in [tier1_result.action, tier2_result.action]:
            final_action = ClassificationAction.REVIEW
            reason = f"Tier 1 and AI disagree, needs review (Tier 1: {tier1_result.action.value}, AI: {tier2_result.action.value})"
        else:
            # Both recommend action, use AI
            final_action = tier2_result.action
            reason = f"Tier 1 and AI disagree on action type, using AI: {tier2_result.reason}"

    # Combine signals from both tiers
    combined_signals = tier1_result.signals + tier2_result.signals

    # Build combined result
    combined_result = ClassificationResult(
        action=final_action,
        confidence=combined_confidence,
        signals=combined_signals,
        reason=reason,
        overridden=tier2_result.overridden,
        override_reason=tier2_result.override_reason
    )

    logger.debug(
        f"Combined Tier 1 + Tier 2: {final_action.value} (confidence={combined_confidence:.2f})",
        extra={
            "tier1_action": tier1_result.action.value,
            "tier1_confidence": tier1_result.confidence,
            "tier2_action": tier2_result.action.value,
            "tier2_confidence": tier2_result.confidence,
            "combined_action": final_action.value,
            "combined_confidence": combined_confidence
        }
    )

    return combined_result


def get_classification_metadata_tier2(
    processing_time_ms: float,
    tokens_used: int,
    cost: float,
    from_cache: bool
) -> ClassificationMetadata:
    """
    Build classification metadata for Tier 2 logging.

    Args:
        processing_time_ms: Time taken to classify (milliseconds)
        tokens_used: OpenAI tokens used
        cost: API cost in USD
        from_cache: Whether result came from cache

    Returns:
        ClassificationMetadata object

    Usage:
        metadata = get_classification_metadata_tier2(
            processing_time_ms=150.5,
            tokens_used=250,
            cost=0.003,
            from_cache=False
        )
    """
    return ClassificationMetadata(
        tier=ClassificationTier.TIER_2,
        processing_time_ms=processing_time_ms,
        model_used=settings.OPENAI_MODEL if not from_cache else "cached",
        cost=cost if not from_cache else 0.0,
        version="1.0"
    )
