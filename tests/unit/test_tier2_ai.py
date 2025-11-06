"""
Unit tests for Tier 2 AI classifier.

Tests OpenAI integration with mocked responses:
- AI classification (trash, archive, keep)
- Response caching in Redis
- Confidence adjustment (reduce by 0.1)
- Error handling (API timeout, invalid JSON)
- Combining Tier 1 + Tier 2 results
- Cost tracking

Run tests:
    pytest tests/unit/test_tier2_ai.py -v
"""

import pytest
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from datetime import datetime

from app.models.email_metadata import EmailMetadata
from app.models.classification import ClassificationResult, ClassificationAction
from app.modules.classifier.tier2_ai import (
    classify_email_tier2,
    combine_tier1_tier2_results,
    get_cache_key,
    get_cached_classification,
    set_cached_classification,
)


# Test fixtures

@pytest.fixture
def sample_metadata():
    """Create sample email metadata for testing."""
    return EmailMetadata(
        message_id="test-message-id",
        thread_id="test-thread-id",
        from_address="deals@oldnavy.com",
        from_name="Old Navy",
        from_domain="oldnavy.com",
        subject="50% Off Everything - Today Only!",
        snippet="Don't miss out on our biggest sale of the year! Shop now and save 50% on all items...",
        gmail_labels=["INBOX", "CATEGORY_PROMOTIONS", "UNREAD"],
        gmail_category="promotional",
        headers={
            "List-Unsubscribe": "<mailto:unsubscribe@oldnavy.com>",
            "Precedence": "bulk",
        },
        received_at=datetime.utcnow()
    )


@pytest.fixture
def mock_openai_classifier():
    """Create a mock OpenAI classifier."""
    with patch('app.modules.classifier.tier2_ai.OpenAIClassifier') as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance
        yield mock_instance


# Test cache key generation

class TestCacheKey:
    """Test cache key generation."""

    def test_get_cache_key(self, sample_metadata):
        """Test cache key generation from metadata."""
        cache_key = get_cache_key(sample_metadata)

        # Should include domain
        assert "oldnavy.com" in cache_key

        # Should have prefix
        assert cache_key.startswith("ai_classification:")

        # Should have 3 parts
        parts = cache_key.split(":")
        assert len(parts) == 3

    def test_get_cache_key_different_subject_same_domain(self):
        """Test that different subjects produce different cache keys."""
        metadata1 = EmailMetadata(
            message_id="msg1",
            thread_id="thread1",
            from_address="deals@example.com",
            from_domain="example.com",
            subject="Sale Today!",
            gmail_labels=[],
            received_at=datetime.utcnow()
        )

        metadata2 = EmailMetadata(
            message_id="msg2",
            thread_id="thread2",
            from_address="news@example.com",
            from_domain="example.com",
            subject="New Products Available",
            gmail_labels=[],
            received_at=datetime.utcnow()
        )

        key1 = get_cache_key(metadata1)
        key2 = get_cache_key(metadata2)

        # Different subjects should produce different keys
        assert key1 != key2


# Test Redis caching

class TestRedisCaching:
    """Test Redis caching functionality."""

    @pytest.mark.asyncio
    async def test_cache_miss_returns_none(self):
        """Test that cache miss returns None."""
        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_redis.return_value = mock_client

            result = await get_cached_classification("test_key")

            assert result is None
            mock_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_cache_hit_returns_result(self):
        """Test that cache hit returns parsed result."""
        import json

        cached_data = {
            "action": "trash",
            "confidence": 0.92,
            "reason": "Promotional email"
        }

        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(cached_data))
            mock_redis.return_value = mock_client

            result = await get_cached_classification("test_key")

            assert result == cached_data
            assert result["action"] == "trash"
            assert result["confidence"] == 0.92

    @pytest.mark.asyncio
    async def test_set_cached_classification(self):
        """Test setting cached classification."""
        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis:
            mock_client = AsyncMock()
            mock_redis.return_value = mock_client

            result_dict = {
                "action": "trash",
                "confidence": 0.90,
                "reason": "Test"
            }

            await set_cached_classification("test_key", result_dict, ttl_days=30)

            # Verify setex was called with TTL
            mock_client.setex.assert_called_once()
            call_args = mock_client.setex.call_args
            assert call_args[0][0] == "test_key"
            assert call_args[0][1] == 30 * 24 * 60 * 60  # 30 days in seconds


# Test AI classification

class TestAIClassification:
    """Test AI-based email classification."""

    @pytest.mark.asyncio
    async def test_classify_email_tier2_with_cache_hit(self, sample_metadata, mock_openai_classifier):
        """Test classification with cache hit (no API call)."""
        import json

        cached_result = {
            "action": "trash",
            "confidence": 0.92,
            "reason": "Promotional email from marketing platform"
        }

        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis, \
             patch('app.modules.classifier.tier2_ai.apply_safety_rails') as mock_safety:

            # Mock Redis cache hit
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=json.dumps(cached_result))
            mock_redis.return_value = mock_client

            # Mock safety rails (no override)
            mock_safety.return_value = (ClassificationAction.TRASH, None)

            result = await classify_email_tier2(sample_metadata)

            # Should use cached result
            assert result.action == ClassificationAction.TRASH
            assert result.confidence == 0.82  # 0.92 - 0.1 (safety reduction)

            # OpenAI API should NOT be called
            mock_openai_classifier.classify_email.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_email_tier2_with_cache_miss(self, sample_metadata, mock_openai_classifier):
        """Test classification with cache miss (calls API)."""
        import json

        ai_response = {
            "action": "trash",
            "confidence": 0.95,
            "reason": "Promotional bulk email with discount offer",
            "tokens_used": 150,
            "cost": 0.003
        }

        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis, \
             patch('app.modules.classifier.tier2_ai.apply_safety_rails') as mock_safety:

            # Mock Redis cache miss
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_redis.return_value = mock_client

            # Mock OpenAI response
            mock_openai_classifier.classify_email = AsyncMock(return_value=ai_response)

            # Mock safety rails (no override)
            mock_safety.return_value = (ClassificationAction.TRASH, None)

            result = await classify_email_tier2(sample_metadata)

            # Should call OpenAI API
            mock_openai_classifier.classify_email.assert_called_once_with(sample_metadata)

            # Should reduce confidence by 0.1
            assert result.action == ClassificationAction.TRASH
            assert result.confidence == 0.85  # 0.95 - 0.1

            # Should cache result
            mock_client.setex.assert_called_once()

    @pytest.mark.asyncio
    async def test_classify_email_tier2_with_ai_error(self, sample_metadata, mock_openai_classifier):
        """Test classification when AI call fails."""
        import json

        ai_error_response = {
            "action": "keep",
            "confidence": 0.0,
            "reason": "AI API error: timeout",
            "tokens_used": 0,
            "cost": 0.0,
            "error": "api_error"
        }

        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis:
            # Mock Redis cache miss
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_redis.return_value = mock_client

            # Mock OpenAI error
            mock_openai_classifier.classify_email = AsyncMock(return_value=ai_error_response)

            result = await classify_email_tier2(sample_metadata)

            # Should return conservative KEEP
            assert result.action == ClassificationAction.KEEP
            assert result.confidence == 0.0
            assert "AI failed" in result.reason

    @pytest.mark.asyncio
    async def test_classify_email_tier2_confidence_reduction(self, sample_metadata, mock_openai_classifier):
        """Test that AI confidence is reduced by 0.1 for safety."""
        import json

        ai_response = {
            "action": "archive",
            "confidence": 0.80,
            "reason": "Transactional email",
            "tokens_used": 120,
            "cost": 0.002
        }

        with patch('app.modules.classifier.tier2_ai.redis.from_url') as mock_redis, \
             patch('app.modules.classifier.tier2_ai.apply_safety_rails') as mock_safety:

            # Mock Redis cache miss
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=None)
            mock_redis.return_value = mock_client

            # Mock OpenAI response
            mock_openai_classifier.classify_email = AsyncMock(return_value=ai_response)

            # Mock safety rails
            mock_safety.return_value = (ClassificationAction.ARCHIVE, None)

            result = await classify_email_tier2(sample_metadata)

            # Confidence should be reduced
            assert result.confidence == 0.70  # 0.80 - 0.1


# Test combining Tier 1 + Tier 2 results

class TestCombineResults:
    """Test combining Tier 1 and Tier 2 classification results."""

    def test_combine_when_both_agree(self):
        """Test combining when both tiers agree on action."""
        from app.models.classification import ClassificationSignal

        tier1_result = ClassificationResult(
            action=ClassificationAction.TRASH,
            confidence=0.75,
            signals=[ClassificationSignal(name="test", score=1.0, reason="test")],
            reason="Tier 1: Promotional email"
        )

        tier2_result = ClassificationResult(
            action=ClassificationAction.TRASH,
            confidence=0.85,
            signals=[ClassificationSignal(name="ai", score=1.0, reason="AI says trash")],
            reason="AI: Promotional bulk email"
        )

        combined = combine_tier1_tier2_results(tier1_result, tier2_result)

        # Should use agreed action
        assert combined.action == ClassificationAction.TRASH

        # Weighted average: (0.75 * 0.4) + (0.85 * 0.6) = 0.81
        assert combined.confidence == pytest.approx(0.81, rel=0.01)

        # Should mention agreement
        assert "agree" in combined.reason.lower()

    def test_combine_when_tiers_disagree(self):
        """Test combining when tiers disagree (conservative approach)."""
        from app.models.classification import ClassificationSignal

        tier1_result = ClassificationResult(
            action=ClassificationAction.TRASH,
            confidence=0.70,
            signals=[ClassificationSignal(name="test", score=1.0, reason="test")],
            reason="Tier 1: Promotional"
        )

        tier2_result = ClassificationResult(
            action=ClassificationAction.KEEP,
            confidence=0.80,
            signals=[ClassificationSignal(name="ai", score=-1.0, reason="AI says keep")],
            reason="AI: Important email"
        )

        combined = combine_tier1_tier2_results(tier1_result, tier2_result)

        # Should choose KEEP (safer action)
        assert combined.action == ClassificationAction.KEEP

        # Should mention disagreement
        assert "disagree" in combined.reason.lower()

    def test_combine_with_confidence_difference(self):
        """Test combining when AI is much more confident."""
        from app.models.classification import ClassificationSignal

        tier1_result = ClassificationResult(
            action=ClassificationAction.REVIEW,
            confidence=0.50,
            signals=[ClassificationSignal(name="test", score=0.5, reason="uncertain")],
            reason="Tier 1: Uncertain"
        )

        tier2_result = ClassificationResult(
            action=ClassificationAction.TRASH,
            confidence=0.95,
            signals=[ClassificationSignal(name="ai", score=1.0, reason="AI confident")],
            reason="AI: Definitely spam"
        )

        combined = combine_tier1_tier2_results(tier1_result, tier2_result)

        # AI is much more confident (0.95 vs 0.50, diff > 0.2)
        # Should use AI action
        assert combined.action == ClassificationAction.TRASH

        # Should mention AI override
        assert "AI override" in combined.reason

    def test_combine_signals_merged(self):
        """Test that signals from both tiers are merged."""
        from app.models.classification import ClassificationSignal

        tier1_result = ClassificationResult(
            action=ClassificationAction.TRASH,
            confidence=0.80,
            signals=[
                ClassificationSignal(name="gmail_category", score=0.6, reason="promotional"),
                ClassificationSignal(name="unsubscribe", score=0.4, reason="has link")
            ],
            reason="Tier 1"
        )

        tier2_result = ClassificationResult(
            action=ClassificationAction.TRASH,
            confidence=0.85,
            signals=[
                ClassificationSignal(name="ai_classification", score=1.0, reason="AI")
            ],
            reason="Tier 2"
        )

        combined = combine_tier1_tier2_results(tier1_result, tier2_result)

        # Should have signals from both tiers
        assert len(combined.signals) == 3
        assert any(s.name == "gmail_category" for s in combined.signals)
        assert any(s.name == "ai_classification" for s in combined.signals)


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
