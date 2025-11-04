"""
Pydantic models for webhook requests and responses.

These models validate incoming webhook payloads from:
- Google Cloud Pub/Sub (Gmail push notifications)
- Future: Stripe webhooks, other integrations
"""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import base64
import json


class PubSubMessage(BaseModel):
    """
    Google Cloud Pub/Sub message format.

    Reference: https://cloud.google.com/pubsub/docs/push
    """
    data: str = Field(..., description="Base64-encoded message data")
    messageId: str = Field(..., description="Unique message ID from Pub/Sub")
    message_id: Optional[str] = Field(None, description="Alias for messageId (snake_case)")
    publishTime: str = Field(..., description="RFC3339 timestamp when message was published")
    publish_time: Optional[str] = Field(None, description="Alias for publishTime (snake_case)")
    attributes: Optional[Dict[str, str]] = Field(default_factory=dict, description="Message attributes")

    @validator("message_id", pre=True, always=True)
    def set_message_id(cls, v, values):
        """Set message_id from messageId if not provided."""
        return v or values.get("messageId")

    @validator("publish_time", pre=True, always=True)
    def set_publish_time(cls, v, values):
        """Set publish_time from publishTime if not provided."""
        return v or values.get("publishTime")

    def decode_data(self) -> Dict[str, Any]:
        """
        Decode base64 data and parse as JSON.

        Returns:
            Decoded message data as dict

        Raises:
            ValueError: If data is not valid base64 or JSON

        Usage:
            message = PubSubMessage(...)
            payload = message.decode_data()
            email_address = payload['emailAddress']
        """
        try:
            # Decode base64
            decoded_bytes = base64.b64decode(self.data)
            decoded_str = decoded_bytes.decode('utf-8')

            # Parse JSON
            return json.loads(decoded_str)

        except (base64.binascii.Error, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to decode Pub/Sub message data: {e}")


class PubSubRequest(BaseModel):
    """
    Google Cloud Pub/Sub push request format.

    This is the top-level request body sent by Pub/Sub to webhook endpoints.
    """
    message: PubSubMessage = Field(..., description="Pub/Sub message")
    subscription: str = Field(..., description="Subscription name that delivered this message")

    class Config:
        schema_extra = {
            "example": {
                "message": {
                    "data": "eyJlbWFpbEFkZHJlc3MiOiJ1c2VyQGdtYWlsLmNvbSIsImhpc3RvcnlJZCI6IjEyMzQ1Njc4OTAifQ==",
                    "messageId": "2070443601311540",
                    "publishTime": "2025-11-04T12:34:56.789Z",
                    "attributes": {}
                },
                "subscription": "projects/my-project/subscriptions/inbox-janitor-gmail-sub"
            }
        }


class GmailWebhookPayload(BaseModel):
    """
    Decoded Gmail push notification payload.

    This is what's inside the base64-encoded Pub/Sub message data.

    Reference: https://developers.google.com/gmail/api/guides/push
    """
    emailAddress: str = Field(..., description="Gmail address that received new mail")
    email_address: Optional[str] = Field(None, description="Alias for emailAddress (snake_case)")
    historyId: str = Field(..., description="Gmail history ID to fetch changes from")
    history_id: Optional[str] = Field(None, description="Alias for historyId (snake_case)")

    @validator("email_address", pre=True, always=True)
    def set_email_address(cls, v, values):
        """Set email_address from emailAddress if not provided."""
        return v or values.get("emailAddress")

    @validator("history_id", pre=True, always=True)
    def set_history_id(cls, v, values):
        """Set history_id from historyId if not provided."""
        return v or values.get("historyId")

    class Config:
        schema_extra = {
            "example": {
                "emailAddress": "user@gmail.com",
                "historyId": "1234567890"
            }
        }


class WebhookResponse(BaseModel):
    """
    Standard webhook response.

    CRITICAL: Webhooks must return 200 OK immediately (within 10ms)
    to prevent Pub/Sub retries. All processing should be asynchronous.
    """
    status: str = Field("success", description="Response status")
    message: Optional[str] = Field(None, description="Optional message")
    task_id: Optional[str] = Field(None, description="Celery task ID if task was enqueued")

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "message": "Webhook received, processing started",
                "task_id": "abc-123-def-456"
            }
        }


class WebhookError(BaseModel):
    """
    Webhook error response.

    IMPORTANT: Even on errors, return 200 OK to prevent retries.
    Only return 4xx/5xx for actual infrastructure failures.
    """
    status: str = Field("error", description="Error status")
    error: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    class Config:
        schema_extra = {
            "example": {
                "status": "error",
                "error": "Invalid message format",
                "details": {"field": "data", "reason": "Not valid base64"}
            }
        }
