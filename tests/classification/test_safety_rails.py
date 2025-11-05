"""
CRITICAL SAFETY TEST: Classification Safety Rails

Tests that safety rails prevent accidental deletion of important emails:
1. Exception keywords (receipt, invoice, interview, medical, etc.)
2. Starred/important emails
3. Recent emails (<3 days)
4. Known contacts
5. Job offers and medical emails

Run before every commit:
    pytest tests/classification/test_safety_rails.py -v
"""

import pytest
from datetime import datetime, timedelta

from app.models.email_metadata import EmailMetadata
from app.models.classification import ClassificationAction
from app.modules.classifier.safety_rails import (
    apply_safety_rails,
    EXCEPTION_KEYWORDS,
    check_exception_keywords,
)
from app.modules.classifier.tier1 import classify_email_tier1


class TestExceptionKeywords:
    """Test that exception keywords prevent TRASH action."""

    def test_receipt_keyword_prevents_trash(self):
        """Test that 'receipt' in subject prevents TRASH."""
        metadata = EmailMetadata(
            message_id="msg_001",
            thread_id="thread_001",
            from_address="store@example.com",
            from_name="Example Store",
            from_domain="example.com",
            subject="Your purchase receipt",
            snippet="Thank you for your order...",
            gmail_labels=["INBOX", "CATEGORY_PROMOTIONS"],
            gmail_category="promotions",
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        # Should NOT be TRASH (even if promotional)
        assert result.action != ClassificationAction.TRASH
        assert result.overridden == True
        assert "exception_keyword" in result.override_reason

    def test_invoice_keyword_prevents_trash(self):
        """Test that 'invoice' in subject prevents TRASH."""
        metadata = EmailMetadata(
            message_id="msg_002",
            thread_id="thread_002",
            from_address="billing@vendor.com",
            from_name="Vendor Billing",
            from_domain="vendor.com",
            subject="Invoice #12345",
            snippet="Your invoice for this month...",
            gmail_labels=["INBOX"],
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        assert result.action != ClassificationAction.TRASH

    def test_interview_keyword_prevents_trash(self):
        """Test that 'interview' in subject prevents TRASH."""
        metadata = EmailMetadata(
            message_id="msg_003",
            thread_id="thread_003",
            from_address="hr@company.com",
            from_name="HR Department",
            from_domain="company.com",
            subject="Interview invitation",
            snippet="We'd like to schedule an interview...",
            gmail_labels=["INBOX"],
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        assert result.action != ClassificationAction.TRASH
        assert result.overridden == True

    def test_medical_keyword_prevents_trash(self):
        """Test that 'medical' in subject prevents TRASH."""
        metadata = EmailMetadata(
            message_id="msg_004",
            thread_id="thread_004",
            from_address="office@hospital.com",
            from_name="Hospital",
            from_domain="hospital.com",
            subject="Medical appointment confirmation",
            snippet="Your appointment is scheduled...",
            gmail_labels=["INBOX"],
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        assert result.action != ClassificationAction.TRASH

    def test_all_exception_keywords_present(self):
        """Test that comprehensive exception keyword list exists."""
        # Critical keywords that must be present
        critical_keywords = [
            'receipt', 'invoice', 'order', 'payment', 'booking',
            'reservation', 'ticket', 'shipped', 'tracking',
            'password', 'security', 'medical', 'interview',
            'job', 'legal', 'bank', 'tax'
        ]

        for keyword in critical_keywords:
            assert keyword in EXCEPTION_KEYWORDS, f"Missing critical keyword: {keyword}"


class TestStarredEmails:
    """Test that starred emails are never trashed."""

    def test_starred_email_prevents_trash(self):
        """Test that starred email is never trashed."""
        metadata = EmailMetadata(
            message_id="msg_005",
            thread_id="thread_005",
            from_address="spam@example.com",
            from_name="Spammer",
            from_domain="example.com",
            subject="50% OFF EVERYTHING!!!",
            snippet="Limited time offer...",
            gmail_labels=["INBOX", "STARRED", "CATEGORY_PROMOTIONS"],
            gmail_category="promotions",
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        # Starred emails should NEVER be trashed
        assert result.action != ClassificationAction.TRASH
        assert result.overridden == True
        assert "starred" in result.override_reason.lower()


class TestImportantEmails:
    """Test that important emails are never trashed."""

    def test_important_label_prevents_trash(self):
        """Test that IMPORTANT label prevents TRASH."""
        metadata = EmailMetadata(
            message_id="msg_006",
            thread_id="thread_006",
            from_address="sender@example.com",
            from_name="Sender",
            from_domain="example.com",
            subject="Promotional email",
            snippet="Check out our sale...",
            gmail_labels=["INBOX", "IMPORTANT", "CATEGORY_PROMOTIONS"],
            gmail_category="promotions",
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        assert result.action != ClassificationAction.TRASH
        assert result.overridden == True


class TestRecentEmails:
    """Test that recent emails are handled cautiously."""

    def test_recent_email_with_low_confidence(self):
        """Test that recent emails with low confidence go to REVIEW."""
        # Email from 1 day ago
        recent_time = datetime.utcnow() - timedelta(days=1)

        metadata = EmailMetadata(
            message_id="msg_007",
            thread_id="thread_007",
            from_address="unknown@example.com",
            from_name="Unknown Sender",
            from_domain="example.com",
            subject="Unclear subject",
            snippet="Some content...",
            gmail_labels=["INBOX"],
            received_at=recent_time,
        )

        result = classify_email_tier1(metadata)

        # Recent + uncertain should be REVIEW, not TRASH
        if result.confidence < 0.85:
            assert result.action == ClassificationAction.REVIEW


class TestJobOfferSafety:
    """CRITICAL: Test that job-related emails are NEVER trashed."""

    def test_job_offer_keywords(self):
        """Test job offer keywords prevent TRASH."""
        job_keywords = ['job', 'interview', 'offer', 'position', 'career', 'hiring', 'recruiter']

        for keyword in job_keywords:
            metadata = EmailMetadata(
                message_id=f"msg_job_{keyword}",
                thread_id=f"thread_job_{keyword}",
                from_address="hr@company.com",
                from_name="HR Department",
                from_domain="company.com",
                subject=f"Your {keyword} application",
                snippet=f"Regarding your {keyword}...",
                gmail_labels=["INBOX"],
                received_at=datetime.utcnow(),
            )

            result = classify_email_tier1(metadata)

            assert result.action != ClassificationAction.TRASH, \
                f"Job keyword '{keyword}' should prevent TRASH"


class TestMedicalEmailSafety:
    """CRITICAL: Test that medical emails are NEVER trashed."""

    def test_medical_keywords(self):
        """Test medical keywords prevent TRASH."""
        medical_keywords = ['medical', 'doctor', 'appointment', 'prescription', 'health', 'hospital', 'clinic']

        for keyword in medical_keywords:
            metadata = EmailMetadata(
                message_id=f"msg_medical_{keyword}",
                thread_id=f"thread_medical_{keyword}",
                from_address=f"{keyword}@hospital.com",
                from_name="Medical Office",
                from_domain="hospital.com",
                subject=f"{keyword.capitalize()} notification",
                snippet=f"Your {keyword} information...",
                gmail_labels=["INBOX"],
                received_at=datetime.utcnow(),
            )

            result = classify_email_tier1(metadata)

            assert result.action != ClassificationAction.TRASH, \
                f"Medical keyword '{keyword}' should prevent TRASH"


class TestFinancialEmailSafety:
    """Test that financial emails are protected."""

    def test_financial_keywords(self):
        """Test financial keywords prevent TRASH."""
        financial_keywords = ['bank', 'tax', 'payment', 'invoice', 'statement', 'balance']

        for keyword in financial_keywords:
            metadata = EmailMetadata(
                message_id=f"msg_financial_{keyword}",
                thread_id=f"thread_financial_{keyword}",
                from_address=f"{keyword}@bank.com",
                from_name="Financial Institution",
                from_domain="bank.com",
                subject=f"Your {keyword} information",
                snippet=f"{keyword.capitalize()} details...",
                gmail_labels=["INBOX"],
                received_at=datetime.utcnow(),
            )

            result = classify_email_tier1(metadata)

            assert result.action != ClassificationAction.TRASH


class TestSafetyRailsFunction:
    """Test the safety rails function directly."""

    def test_safety_rails_override_trash(self):
        """Test that safety rails can override TRASH action."""
        metadata = EmailMetadata(
            message_id="msg_008",
            thread_id="thread_008",
            from_address="sender@example.com",
            from_name="Sender",
            from_domain="example.com",
            subject="Receipt for your order",  # Exception keyword
            snippet="Thank you for your purchase...",
            gmail_labels=["INBOX", "CATEGORY_PROMOTIONS"],
            received_at=datetime.utcnow(),
        )

        # Proposed action is TRASH
        proposed_action = ClassificationAction.TRASH

        # Apply safety rails
        final_action, override_reason = apply_safety_rails(metadata, proposed_action)

        # Should be overridden
        assert final_action != ClassificationAction.TRASH
        assert override_reason is not None
        assert "exception_keyword" in override_reason

    def test_safety_rails_allow_keep(self):
        """Test that safety rails don't override KEEP action."""
        metadata = EmailMetadata(
            message_id="msg_009",
            thread_id="thread_009",
            from_address="friend@example.com",
            from_name="Friend",
            from_domain="example.com",
            subject="Hey there!",
            snippet="Personal email...",
            gmail_labels=["INBOX"],
            received_at=datetime.utcnow(),
        )

        # Proposed action is KEEP
        proposed_action = ClassificationAction.KEEP

        # Apply safety rails
        final_action, override_reason = apply_safety_rails(metadata, proposed_action)

        # Should not be overridden
        assert final_action == ClassificationAction.KEEP
        assert override_reason is None


class TestHasExceptionKeyword:
    """Test the check_exception_keywords helper function."""

    def test_detects_keyword_in_subject(self):
        """Test that exception keywords are detected in subject."""
        metadata = EmailMetadata(
            message_id="test1", thread_id="thread1",
            from_address="test@example.com", from_name="Test", from_domain="example.com",
            subject="Your receipt for order #123", received_at=datetime.utcnow()
        )
        assert check_exception_keywords(metadata) is not None

    def test_detects_keyword_in_snippet(self):
        """Test that exception keywords are detected in snippet."""
        metadata = EmailMetadata(
            message_id="test2", thread_id="thread2",
            from_address="test@example.com", from_name="Test", from_domain="example.com",
            subject="Update", snippet="Your password reset link", received_at=datetime.utcnow()
        )
        assert check_exception_keywords(metadata) is not None

    def test_case_insensitive(self):
        """Test that keyword detection is case-insensitive."""
        metadata = EmailMetadata(
            message_id="test3", thread_id="thread3",
            from_address="test@example.com", from_name="Test", from_domain="example.com",
            subject="RECEIPT for purchase", received_at=datetime.utcnow()
        )
        assert check_exception_keywords(metadata) is not None

    def test_no_false_positives(self):
        """Test that normal words don't trigger exception."""
        metadata = EmailMetadata(
            message_id="test4", thread_id="thread4",
            from_address="test@example.com", from_name="Test", from_domain="example.com",
            subject="Check out our sale!", snippet="Limited time offer", received_at=datetime.utcnow()
        )
        assert check_exception_keywords(metadata) is None
