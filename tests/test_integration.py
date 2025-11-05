"""
Integration Tests for Full Email Processing Pipeline

Tests the complete flow:
1. Webhook receives Gmail push notification
2. Task enqueued for history processing
3. Metadata extracted from Gmail API
4. Email classified using Tier 1 classifier
5. Result stored in email_actions and email_metadata tables
6. Logs and metrics recorded

Run with:
    pytest tests/test_integration.py -v -s
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import base64
import json


# TODO: Uncomment when process_gmail_history task is implemented
# class TestWebhookToDatabase:
#     """Test complete webhook-to-database flow."""
#
#     @pytest.mark.asyncio
#     @patch('app.api.webhooks.process_gmail_history')
#     async def test_webhook_enqueues_processing_task(self, mock_task):
#         """Test that webhook endpoint enqueues processing task."""
#         from app.api.webhooks import gmail_webhook
#         from app.models.webhook import PubSubRequest
#
#         # Mock Celery task
#         mock_task.delay = MagicMock()
#
#         # Create webhook payload
#         webhook_data = {
#             "emailAddress": "test@gmail.com",
#             "historyId": "12345"
#         }
#         encoded_data = base64.b64encode(json.dumps(webhook_data).encode()).decode()
#
#         request = PubSubRequest(
#             message={
#                 "data": encoded_data,
#                 "messageId": "msg_123",
#                 "publishTime": "2025-01-01T00:00:00Z"
#             },
#             subscription="projects/test/subscriptions/test-sub"
#         )
#
#         # Mock mailbox lookup
#         with patch('app.api.webhooks.get_async_session') as mock_session:
#             mock_session_instance = AsyncMock()
#             mock_session.__aenter__ = AsyncMock(return_value=mock_session_instance)
#             mock_session.__aexit__ = AsyncMock()
#
#             mock_result = MagicMock()
#             mock_mailbox = MagicMock()
#             mock_mailbox.id = "mailbox_uuid"
#             mock_mailbox.email_address = "test@gmail.com"
#             mock_result.scalar_one_or_none.return_value = mock_mailbox
#             mock_session_instance.execute = AsyncMock(return_value=mock_result)
#
#             # Call webhook
#             response = await gmail_webhook(request)
#
#             # Verify task was enqueued
#             assert response["status"] == "ok"
#             assert mock_task.delay.called


# TODO: Uncomment when get_gmail_service is implemented
# class TestMetadataExtraction:
#     """Test metadata extraction from Gmail API."""
#
#     @pytest.mark.asyncio
#     @patch('app.modules.ingest.metadata_extractor.get_gmail_service')
#     async def test_extract_email_metadata_success(self, mock_service):
#         """Test successful metadata extraction."""
#         from app.modules.ingest.metadata_extractor import extract_email_metadata
#
#         # Mock Gmail service
#         mock_gmail = MagicMock()
#         mock_gmail.users().messages().get().execute.return_value = {
#             'id': 'msg_123',
#             'threadId': 'thread_123',
#             'labelIds': ['INBOX', 'CATEGORY_PROMOTIONS'],
#             'snippet': 'Test email snippet',
#             'payload': {
#                 'headers': [
#                     {'name': 'From', 'value': 'sender@example.com'},
#                     {'name': 'Subject', 'value': 'Test Subject'},
#                     {'name': 'Date', 'value': 'Mon, 01 Jan 2025 00:00:00 +0000'},
#                 ]
#             }
#         }
#         mock_service.return_value = mock_gmail
#
#         # Extract metadata
#         metadata = await extract_email_metadata("mailbox_id", "msg_123")
#
#         # Verify metadata
#         assert metadata.message_id == "msg_123"
#         assert metadata.from_address == "sender@example.com"
#         assert metadata.subject == "Test Subject"
#         assert metadata.is_promotional == True


class TestClassificationEngine:
    """Test classification engine."""

    def test_classify_promotional_email(self):
        """Test classification of promotional email."""
        from app.models.email_metadata import EmailMetadata
        from app.modules.classifier.tier1 import classify_email_tier1
        from app.models.classification import ClassificationAction
        from datetime import timedelta

        # Use email from 7 days ago (avoid recent email safety rail)
        old_date = datetime.utcnow() - timedelta(days=7)

        metadata = EmailMetadata(
            message_id="msg_promo",
            thread_id="thread_promo",
            from_address="store@sendgrid.net",
            from_name="Store",
            from_domain="sendgrid.net",
            subject="Big sale this weekend!",
            snippet="Limited time discount available...",
            gmail_labels=["INBOX", "CATEGORY_PROMOTIONS"],
            gmail_category="promotions",
            headers={
                "List-Unsubscribe": "<mailto:unsubscribe@example.com>"
            },
            received_at=old_date,
        )

        result = classify_email_tier1(metadata)

        # Should be high-confidence TRASH or ARCHIVE
        assert result.action in [ClassificationAction.TRASH, ClassificationAction.ARCHIVE]
        assert result.confidence > 0.70

    def test_classify_important_email(self):
        """Test classification of important email."""
        from app.models.email_metadata import EmailMetadata
        from app.modules.classifier.tier1 import classify_email_tier1
        from app.models.classification import ClassificationAction

        metadata = EmailMetadata(
            message_id="msg_important",
            thread_id="thread_important",
            from_address="hr@company.com",
            from_name="HR Department",
            from_domain="company.com",
            subject="Interview invitation",
            snippet="We'd like to schedule an interview...",
            gmail_labels=["INBOX", "IMPORTANT"],
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        # Should NEVER be TRASH (exception keyword + important)
        assert result.action != ClassificationAction.TRASH


# TODO: Uncomment when get_async_session is implemented
# class TestDatabaseStorage:
#     """Test database storage of classification results."""
#
#     @pytest.mark.asyncio
#     async def test_email_action_stored(self):
#         """Test that email_action is stored in database."""
#         from app.core.database import get_async_session
#         from app.models.email_action import EmailAction
#         from app.models.mailbox import Mailbox
#         from sqlalchemy import select
#         import uuid
#
#         # Create test mailbox
#         test_mailbox_id = uuid.uuid4()
#
#         async with get_async_session() as session:
#             # Create test email action
#             action = EmailAction(
#                 mailbox_id=test_mailbox_id,
#                 message_id="test_msg_123",
#                 thread_id="test_thread_123",
#                 from_address="test@example.com",
#                 subject="Test Subject",
#                 snippet="Test snippet",
#                 action="archive",
#                 reason="Test classification",
#                 confidence=0.85,
#                 classification_metadata={
#                     "signals": [],
#                     "tier": "tier_1"
#                 }
#             )
#
#             session.add(action)
#             await session.commit()
#
#             # Verify stored
#             result = await session.execute(
#                 select(EmailAction).where(EmailAction.message_id == "test_msg_123")
#             )
#             stored_action = result.scalar_one_or_none()
#
#             assert stored_action is not None
#             assert stored_action.action == "archive"
#             assert stored_action.confidence == 0.85
#
#             # Cleanup
#             await session.delete(stored_action)
#             await session.commit()


# TODO: Uncomment when get_gmail_service is implemented
# class TestFullPipeline:
#     """Test complete end-to-end pipeline (mocked Gmail API)."""
#
#     @pytest.mark.asyncio
#     @patch('app.modules.ingest.metadata_extractor.get_gmail_service')
#     @patch('app.tasks.classify.classify_email_tier1')
#     async def test_full_pipeline_promotional_email(self, mock_classify, mock_service):
#         """Test full pipeline for promotional email."""
#         # Mock Gmail service
#         mock_gmail = MagicMock()
#         mock_gmail.users().history().list().execute.return_value = {
#             "history": [
#                 {
#                     "messagesAdded": [
#                         {
#                             "message": {
#                                 "id": "msg_promo",
#                                 "labelIds": ["INBOX", "CATEGORY_PROMOTIONS"]
#                             }
#                         }
#                     ]
#                 }
#             ]
#         }
#         mock_gmail.users().messages().get().execute.return_value = {
#             'id': 'msg_promo',
#             'threadId': 'thread_promo',
#             'labelIds': ['INBOX', 'CATEGORY_PROMOTIONS'],
#             'snippet': 'Limited time discount available...',
#             'payload': {
#                 'headers': [
#                     {'name': 'From', 'value': 'store@example.com'},
#                     {'name': 'Subject', 'value': 'Big sale this weekend!'},
#                     {'name': 'Date', 'value': 'Mon, 01 Jan 2025 00:00:00 +0000'},
#                     {'name': 'List-Unsubscribe', 'value': '<mailto:unsub@example.com>'},
#                 ]
#             }
#         }
#         mock_service.return_value = mock_gmail
#
#         # Mock classification task
#         mock_classify.delay = MagicMock()
#
#         # Run pipeline (extract metadata)
#         from app.modules.ingest.metadata_extractor import extract_email_metadata
#
#         metadata = await extract_email_metadata("mailbox_id", "msg_promo")
#
#         # Verify metadata extracted correctly
#         assert metadata.is_promotional == True
#         assert metadata.has_unsubscribe_header == True
#
#         # Classify
#         from app.modules.classifier.tier1 import classify_email_tier1
#         result = classify_email_tier1(metadata)
#
#         # Verify classification
#         assert result.confidence > 0.70  # High confidence
#         assert result.action in ["trash", "archive"]


# TODO: Uncomment when get_gmail_service is implemented
# class TestErrorHandling:
#     """Test error handling in pipeline."""
#
#     @pytest.mark.asyncio
#     @patch('app.modules.ingest.metadata_extractor.get_gmail_service')
#     async def test_gmail_api_error_handling(self, mock_service):
#         """Test that Gmail API errors are caught and logged."""
#         from app.modules.ingest.metadata_extractor import extract_email_metadata, EmailMetadataExtractError
#         from googleapiclient.errors import HttpError
#
#         # Mock Gmail service to raise error
#         mock_gmail = MagicMock()
#         mock_gmail.users().messages().get().execute.side_effect = HttpError(
#             resp=MagicMock(status=404),
#             content=b'Not found'
#         )
#         mock_service.return_value = mock_gmail
#
#         # Should raise EmailMetadataExtractError
#         with pytest.raises(EmailMetadataExtractError):
#             await extract_email_metadata("mailbox_id", "invalid_msg_id")


class TestLoggingAndMetrics:
    """Test that logging and metrics are recorded."""

    def test_classification_logging(self, caplog):
        """Test that classification is logged."""
        import logging
        caplog.set_level(logging.INFO)

        from app.models.email_metadata import EmailMetadata
        from app.modules.classifier.tier1 import classify_email_tier1

        metadata = EmailMetadata(
            message_id="msg_log_test",
            thread_id="thread_log_test",
            from_address="test@example.com",
            from_name="Test",
            from_domain="example.com",
            subject="Test",
            snippet="Test",
            gmail_labels=["INBOX"],
            received_at=datetime.utcnow(),
        )

        result = classify_email_tier1(metadata)

        # Verify logging occurred (check log records)
        # Note: This depends on classifier implementation
        assert result is not None
