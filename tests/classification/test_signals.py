"""
Classification Signal Calculation Tests

Tests that classification signals are calculated correctly:
1. Gmail category signals
2. Unsubscribe header signals
3. Bulk mail signals
4. Marketing domain signals
5. Subject pattern signals

Run to verify classifier logic:
    pytest tests/classification/test_signals.py -v
"""

import pytest
from datetime import datetime

from app.models.email_metadata import EmailMetadata
from app.modules.classifier.signals import (
    signal_gmail_category,
    signal_list_unsubscribe,
    signal_bulk_headers,
    signal_sender_domain,
    signal_subject_patterns,
    signal_starred_or_important,
    signal_receipt_indicators,
    calculate_all_signals,
)
from app.models.classification import ClassificationSignal


class TestGmailCategorySignal:
    """Test Gmail category signal calculation."""

    def test_promotional_category_high_score(self):
        """Test that CATEGORY_PROMOTIONS gives high trash score."""
        metadata = EmailMetadata(
            message_id="msg_001",
            thread_id="thread_001",
            from_address="store@example.com",
            from_name="Store",
            from_domain="example.com",
            subject="Sale!",
            gmail_labels=["INBOX", "CATEGORY_PROMOTIONS"],
            gmail_category="promotions",
            received_at=datetime.utcnow(),
        )

        signal = signal_gmail_category(metadata)

        assert signal.score > 0.5  # Strong trash indicator
        assert signal.weight == 1.0  # High confidence
        assert "promotions" in signal.reason.lower()

    def test_personal_category_negative_score(self):
        """Test that personal category gives negative score (keep indicator)."""
        metadata = EmailMetadata(
            message_id="msg_002",
            thread_id="thread_002",
            from_address="friend@example.com",
            from_name="Friend",
            from_domain="example.com",
            subject="Hey!",
            gmail_labels=["INBOX"],
            gmail_category="personal",
            received_at=datetime.utcnow(),
        )

        signal = signal_gmail_category(metadata)

        assert signal.score < 0  # Keep indicator

    def test_social_category_moderate_score(self):
        """Test that CATEGORY_SOCIAL gives moderate score."""
        metadata = EmailMetadata(
            message_id="msg_003",
            thread_id="thread_003",
            from_address="notify@linkedin.com",
            from_name="LinkedIn",
            from_domain="linkedin.com",
            subject="You appeared in searches",
            gmail_labels=["INBOX", "CATEGORY_SOCIAL"],
            gmail_category="social",
            received_at=datetime.utcnow(),
        )

        signal = signal_gmail_category(metadata)

        assert signal.score > 0  # Trash indicator
        assert signal.score < 0.6  # But not as strong as promotions


class TestUnsubscribeHeaderSignal:
    """Test List-Unsubscribe header signal."""

    def test_unsubscribe_header_present(self):
        """Test that List-Unsubscribe header gives high score."""
        metadata = EmailMetadata(
            message_id="msg_004",
            thread_id="thread_004",
            from_address="newsletter@example.com",
            from_name="Newsletter",
            from_domain="example.com",
            subject="Weekly digest",
            headers={
                "List-Unsubscribe": "<mailto:unsubscribe@example.com>"
            },
            received_at=datetime.utcnow(),
        )

        signal = signal_unsubscribe_header(metadata)

        assert signal.score > 0.7  # Very strong trash indicator
        assert "unsubscribe" in signal.reason.lower()

    def test_no_unsubscribe_header(self):
        """Test that missing List-Unsubscribe gives zero score."""
        metadata = EmailMetadata(
            message_id="msg_005",
            thread_id="thread_005",
            from_address="friend@example.com",
            from_name="Friend",
            from_domain="example.com",
            subject="Hi",
            headers={},
            received_at=datetime.utcnow(),
        )

        signal = signal_unsubscribe_header(metadata)

        assert signal.score == 0.0


class TestBulkMailHeadersSignal:
    """Test bulk mail headers signal."""

    def test_precedence_bulk_header(self):
        """Test that Precedence: bulk header gives high score."""
        metadata = EmailMetadata(
            message_id="msg_006",
            thread_id="thread_006",
            from_address="bulk@example.com",
            from_name="Bulk Sender",
            from_domain="example.com",
            subject="Mass email",
            headers={
                "Precedence": "bulk"
            },
            received_at=datetime.utcnow(),
        )

        signal = signal_bulk_mail_headers(metadata)

        assert signal.score > 0.5
        assert "bulk" in signal.reason.lower()

    def test_auto_submitted_header(self):
        """Test that Auto-Submitted header gives moderate score."""
        metadata = EmailMetadata(
            message_id="msg_007",
            thread_id="thread_007",
            from_address="auto@example.com",
            from_name="Auto Sender",
            from_domain="example.com",
            subject="Automated email",
            headers={
                "Auto-Submitted": "auto-generated"
            },
            received_at=datetime.utcnow(),
        )

        signal = signal_bulk_mail_headers(metadata)

        assert signal.score > 0


class TestMarketingDomainSignal:
    """Test marketing platform domain signal."""

    def test_sendgrid_domain(self):
        """Test that sendgrid.net domain gives high score."""
        metadata = EmailMetadata(
            message_id="msg_008",
            thread_id="thread_008",
            from_address="sender@sendgrid.net",
            from_name="Sender",
            from_domain="sendgrid.net",
            subject="Marketing email",
            received_at=datetime.utcnow(),
        )

        signal = signal_marketing_domain(metadata)

        assert signal.score > 0.5
        assert "sendgrid" in signal.reason.lower()

    def test_mailchimp_domain(self):
        """Test that mailchimp.com domain gives high score."""
        metadata = EmailMetadata(
            message_id="msg_009",
            thread_id="thread_009",
            from_address="sender@mailchimp.com",
            from_name="Sender",
            from_domain="mailchimp.com",
            subject="Newsletter",
            received_at=datetime.utcnow(),
        )

        signal = signal_marketing_domain(metadata)

        assert signal.score > 0.5

    def test_normal_domain(self):
        """Test that normal domain gives zero score."""
        metadata = EmailMetadata(
            message_id="msg_010",
            thread_id="thread_010",
            from_address="sender@example.com",
            from_name="Sender",
            from_domain="example.com",
            subject="Email",
            received_at=datetime.utcnow(),
        )

        signal = signal_marketing_domain(metadata)

        assert signal.score == 0.0


class TestSubjectPatternsSignal:
    """Test subject pattern matching signal."""

    def test_percentage_off_pattern(self):
        """Test that '% off' in subject gives high score."""
        metadata = EmailMetadata(
            message_id="msg_011",
            thread_id="thread_011",
            from_address="store@example.com",
            from_name="Store",
            from_domain="example.com",
            subject="50% off everything!",
            received_at=datetime.utcnow(),
        )

        signal = signal_subject_patterns(metadata)

        assert signal.score > 0.4
        assert "marketing" in signal.reason.lower()

    def test_limited_time_pattern(self):
        """Test that 'limited time' pattern gives high score."""
        metadata = EmailMetadata(
            message_id="msg_012",
            thread_id="thread_012",
            from_address="store@example.com",
            from_name="Store",
            from_domain="example.com",
            subject="Limited time offer - Act now!",
            received_at=datetime.utcnow(),
        )

        signal = signal_subject_patterns(metadata)

        assert signal.score > 0.4

    def test_excessive_emojis(self):
        """Test that excessive emojis give moderate score."""
        metadata = EmailMetadata(
            message_id="msg_013",
            thread_id="thread_013",
            from_address="store@example.com",
            from_name="Store",
            from_domain="example.com",
            subject="🎉🎉🎉 SALE 🎉🎉🎉",
            received_at=datetime.utcnow(),
        )

        signal = signal_subject_patterns(metadata)

        assert signal.score > 0

    def test_normal_subject(self):
        """Test that normal subject gives zero score."""
        metadata = EmailMetadata(
            message_id="msg_014",
            thread_id="thread_014",
            from_address="friend@example.com",
            from_name="Friend",
            from_domain="example.com",
            subject="Hey, how are you?",
            received_at=datetime.utcnow(),
        )

        signal = signal_subject_patterns(metadata)

        assert signal.score == 0.0


class TestSenderEngagementSignal:
    """Test sender engagement signal (requires user settings/stats)."""

    def test_never_opened_sender(self):
        """Test that never-opened sender gives high score."""
        # This test would require sender_stats database access
        # For now, test the function with mock data
        metadata = EmailMetadata(
            message_id="msg_015",
            thread_id="thread_015",
            from_address="spam@example.com",
            from_name="Spammer",
            from_domain="example.com",
            subject="Spam",
            received_at=datetime.utcnow(),
        )

        # Without sender stats, should return neutral signal
        signal = signal_sender_engagement(metadata, sender_stats=None)

        assert signal.score == 0.0  # Neutral when no stats


class TestRecentEmailSignal:
    """Test recent email signal."""

    def test_very_recent_email(self):
        """Test that emails from today get negative score (keep)."""
        from datetime import timedelta

        recent = datetime.utcnow() - timedelta(hours=2)

        metadata = EmailMetadata(
            message_id="msg_016",
            thread_id="thread_016",
            from_address="sender@example.com",
            from_name="Sender",
            from_domain="example.com",
            subject="Recent email",
            received_at=recent,
        )

        signal = signal_recent_email(metadata)

        assert signal.score < 0  # Negative = keep indicator

    def test_old_email(self):
        """Test that old emails get zero score."""
        from datetime import timedelta

        old = datetime.utcnow() - timedelta(days=10)

        metadata = EmailMetadata(
            message_id="msg_017",
            thread_id="thread_017",
            from_address="sender@example.com",
            from_name="Sender",
            from_domain="example.com",
            subject="Old email",
            received_at=old,
        )

        signal = signal_recent_email(metadata)

        assert signal.score == 0.0  # Neutral for old emails
