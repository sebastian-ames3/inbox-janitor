"""
CRITICAL SECURITY TEST: No Email Body Sent to AI

Tests that AI classification NEVER receives full email bodies:
1. Only sends minimal metadata (sender, subject, snippet max 200 chars)
2. Prompt length is reasonable (<3000 chars)
3. EmailMetadata snippet is truncated to 200 chars
4. Security check method validates no body content

Run before every commit involving AI:
    pytest tests/security/test_ai_no_body.py -v
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from app.models.email_metadata import EmailMetadata
from app.modules.classifier.openai_client import OpenAIClassifier


# Test fixtures

@pytest.fixture
def sample_metadata_short_snippet():
    """Create email metadata with short snippet (safe)."""
    return EmailMetadata(
        message_id="test-msg-1",
        thread_id="test-thread-1",
        from_address="sender@example.com",
        from_domain="example.com",
        subject="Test Email",
        snippet="This is a short snippet of 50 characters long!!",
        gmail_labels=["INBOX"],
        gmail_category="personal",
        headers={},
        received_at=datetime.utcnow()
    )


@pytest.fixture
def sample_metadata_long_snippet():
    """Create email metadata with long snippet that should be truncated."""
    # Create a snippet longer than 200 chars (but EmailMetadata should truncate it)
    long_snippet = "A" * 500  # 500 chars

    return EmailMetadata(
        message_id="test-msg-2",
        thread_id="test-thread-2",
        from_address="sender@example.com",
        from_domain="example.com",
        subject="Test Email with Long Content",
        snippet=long_snippet,  # Will be truncated by EmailMetadata validator
        gmail_labels=["INBOX"],
        gmail_category="personal",
        headers={},
        received_at=datetime.utcnow()
    )


@pytest.fixture
def sample_metadata_sensitive_content():
    """Create email metadata with sensitive content (to test it's NOT sent to AI)."""
    return EmailMetadata(
        message_id="test-msg-3",
        thread_id="test-thread-3",
        from_address="bank@chase.com",
        from_domain="chase.com",
        subject="Your Chase Account Statement",
        snippet="Account number: 1234-5678-9012. Balance: $15,234.56. Recent transactions: Walmart $45.67, Amazon $123.45...",
        gmail_labels=["INBOX"],
        gmail_category="personal",
        headers={},
        received_at=datetime.utcnow()
    )


# Security Tests

class TestAIPromptSecurity:
    """Test that AI prompts contain NO full email bodies."""

    def test_prompt_contains_no_full_body(self, sample_metadata_short_snippet):
        """Test that prompt built from metadata doesn't contain full body."""
        classifier = OpenAIClassifier()
        prompt = classifier._build_classification_prompt(sample_metadata_short_snippet)

        # Prompt should contain metadata only
        assert "From: sender@example.com" in prompt
        assert "Subject: Test Email" in prompt

        # Snippet should be present but truncated
        assert sample_metadata_short_snippet.snippet in prompt

        # Prompt should NOT contain any indication of full body
        forbidden_phrases = [
            "full body",
            "complete email",
            "entire message",
            "all content",
            "html_body",
            "raw_content"
        ]

        for phrase in forbidden_phrases:
            assert phrase not in prompt.lower(), f"Prompt contains forbidden phrase: {phrase}"

    def test_prompt_length_reasonable(self, sample_metadata_short_snippet):
        """Test that prompt length is reasonable (not full email body)."""
        classifier = OpenAIClassifier()
        prompt = classifier._build_classification_prompt(sample_metadata_short_snippet)

        # Prompt should be <3000 chars if only using metadata
        assert len(prompt) < 3000, f"Prompt too long ({len(prompt)} chars) - may contain full body"

    def test_snippet_truncated_in_metadata(self, sample_metadata_long_snippet):
        """Test that EmailMetadata automatically truncates snippet to 200 chars."""
        # EmailMetadata should have truncated the snippet
        assert len(sample_metadata_long_snippet.snippet) <= 200, \
            f"Snippet not truncated: {len(sample_metadata_long_snippet.snippet)} chars"

    def test_prompt_snippet_max_200_chars(self, sample_metadata_long_snippet):
        """Test that snippet in prompt is max 200 chars."""
        classifier = OpenAIClassifier()
        prompt = classifier._build_classification_prompt(sample_metadata_long_snippet)

        # Extract snippet from prompt (between "Snippet: " and next line)
        import re
        match = re.search(r'Snippet: (.+?)(?:\n|$)', prompt)

        if match:
            snippet_in_prompt = match.group(1).strip()

            # Verify snippet is truncated
            assert len(snippet_in_prompt) <= 200, \
                f"Snippet in prompt too long: {len(snippet_in_prompt)} chars"

    def test_sensitive_data_in_snippet_still_truncated(self, sample_metadata_sensitive_content):
        """Test that even with sensitive data, snippet is truncated (not removed entirely)."""
        # We WANT snippet to be sent (it's necessary for classification)
        # But it must be truncated to 200 chars max
        assert len(sample_metadata_sensitive_content.snippet) <= 200

        classifier = OpenAIClassifier()
        prompt = classifier._build_classification_prompt(sample_metadata_sensitive_content)

        # Prompt should contain truncated snippet
        assert "Account number:" in prompt or "Your Chase Account Statement" in prompt

        # But the full account number might be truncated
        assert len(prompt) < 3000


class TestAISecurityCheck:
    """Test the built-in security check method."""

    def test_verify_no_body_in_prompt_valid(self, sample_metadata_short_snippet):
        """Test that security check passes for valid metadata."""
        classifier = OpenAIClassifier()
        is_safe = classifier.verify_no_body_in_prompt(sample_metadata_short_snippet)

        assert is_safe is True

    def test_verify_no_body_in_prompt_too_long_snippet(self):
        """Test that security check fails if snippet is too long."""
        # Manually create metadata with long snippet (bypassing validator for test)
        # Use model_construct() to bypass Pydantic validators (works in v1 and v2)
        metadata = EmailMetadata.model_construct(
            message_id="test",
            thread_id="test",
            from_address="test@example.com",
            from_domain="example.com",
            subject="Test",
            snippet="A" * 500,  # 500 chars (too long)
            gmail_labels=[],
            gmail_category="personal",
            headers={},
            received_at=datetime.utcnow()
        )

        classifier = OpenAIClassifier()
        is_safe = classifier.verify_no_body_in_prompt(metadata)

        # Security check should fail
        assert is_safe is False


class TestAIDataMinimization:
    """Test that AI receives minimal data necessary for classification."""

    def test_prompt_contains_only_required_fields(self, sample_metadata_short_snippet):
        """Test that prompt contains only required fields (sender, subject, snippet, headers)."""
        classifier = OpenAIClassifier()
        prompt = classifier._build_classification_prompt(sample_metadata_short_snippet)

        # Required fields
        required_fields = [
            "From:",
            "Subject:",
            "Snippet:",
            "Has unsubscribe link:",
            "Gmail category:"
        ]

        for field in required_fields:
            assert field in prompt, f"Required field missing: {field}"

        # Fields that should NOT be in prompt
        forbidden_fields = [
            "thread_id",
            "message_id",
            "gmail_labels",  # Raw label IDs (privacy)
            "received_at",  # Exact timestamp (privacy)
            "headers",  # Full headers (too much data)
        ]

        for field in forbidden_fields:
            # Check field name doesn't appear in prompt
            # (field values might appear, but not the field names)
            assert field not in prompt.lower(), f"Forbidden field found in prompt: {field}"

    def test_prompt_does_not_include_personal_identifiers(self):
        """Test that prompt doesn't include unnecessary personal identifiers."""
        metadata = EmailMetadata(
            message_id="18c3f2a1b2c3d4e5",  # Gmail message ID
            thread_id="thread-12345",
            from_address="sender@example.com",
            from_domain="example.com",
            subject="Test",
            snippet="Test snippet",
            gmail_labels=["INBOX", "UNREAD", "CATEGORY_PROMOTIONS"],
            gmail_category="promotional",
            headers={},
            received_at=datetime.utcnow()
        )

        classifier = OpenAIClassifier()
        prompt = classifier._build_classification_prompt(metadata)

        # Gmail message IDs should NOT be in prompt (unnecessary, privacy risk)
        assert "18c3f2a1b2c3d4e5" not in prompt
        assert "thread-12345" not in prompt

        # Label IDs should NOT be in prompt (internal identifiers)
        assert "UNREAD" not in prompt


class TestEmailMetadataValidation:
    """Test that EmailMetadata model enforces security constraints."""

    def test_snippet_validator_truncates(self):
        """Test that EmailMetadata automatically truncates long snippets."""
        long_snippet = "A" * 500

        metadata = EmailMetadata(
            message_id="test",
            thread_id="test",
            from_address="test@example.com",
            from_domain="example.com",
            subject="Test",
            snippet=long_snippet,
            gmail_labels=[],
            gmail_category="personal",
            headers={},
            received_at=datetime.utcnow()
        )

        # Should be truncated to 200 chars
        assert len(metadata.snippet) == 200

    def test_subject_validator_truncates(self):
        """Test that EmailMetadata truncates long subjects."""
        long_subject = "A" * 600

        metadata = EmailMetadata(
            message_id="test",
            thread_id="test",
            from_address="test@example.com",
            from_domain="example.com",
            subject=long_subject,
            gmail_labels=[],
            gmail_category="personal",
            headers={},
            received_at=datetime.utcnow()
        )

        # Should be truncated to 500 chars
        assert len(metadata.subject) == 500


class TestOpenAIResponseFormat:
    """Test that OpenAI API is configured to prevent body data leaks."""

    def test_openai_max_tokens_limited(self):
        """Test that OpenAI max_tokens is limited (prevents long responses)."""
        # This is a code inspection test
        import inspect
        from app.modules.classifier.openai_client import OpenAIClassifier

        # Get classify_email method source
        source = inspect.getsource(OpenAIClassifier.classify_email)

        # Verify max_tokens is set and is reasonable (<200)
        assert "max_tokens" in source, "max_tokens not configured in OpenAI call"
        assert "max_tokens=150" in source or "max_tokens = 150" in source, \
            "max_tokens should be 150 (short responses only)"

    def test_openai_uses_json_format(self):
        """Test that OpenAI response format is JSON (prevents verbose responses)."""
        import inspect
        from app.modules.classifier.openai_client import OpenAIClassifier

        # Get classify_email method source
        source = inspect.getsource(OpenAIClassifier.classify_email)

        # Verify JSON format is enforced
        assert 'response_format' in source and 'json_object' in source, \
            "OpenAI should use JSON response format"


# Integration test

class TestAIClassificationEndToEnd:
    """End-to-end test of AI classification (mocked OpenAI)."""

    @pytest.mark.asyncio
    async def test_ai_classification_with_mocked_openai(self, sample_metadata_short_snippet):
        """Test AI classification with mocked OpenAI (verify no body sent)."""
        with patch('app.modules.classifier.openai_client.OpenAI') as mock_openai_class:
            # Mock OpenAI response
            mock_client = Mock()
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content='{"action": "trash", "confidence": 0.90, "reason": "Promotional email"}'))]
            mock_response.usage = Mock(total_tokens=150)
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai_class.return_value = mock_client

            # Run classification
            classifier = OpenAIClassifier()
            result = await classifier.classify_email(sample_metadata_short_snippet)

            # Get the prompt that was sent
            call_args = mock_client.chat.completions.create.call_args
            messages = call_args[1]['messages']
            user_message = messages[1]['content']

            # Verify prompt is short and contains only metadata
            assert len(user_message) < 3000
            assert "From: sender@example.com" in user_message
            assert sample_metadata_short_snippet.snippet in user_message

            # Verify NO body keywords
            assert "full body" not in user_message.lower()
            assert "complete email" not in user_message.lower()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
