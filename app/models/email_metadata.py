"""
Email metadata models (Pydantic for validation, NOT database models).

These models represent email metadata extracted from Gmail API.
They are used for processing and classification, then stored in the database.

CRITICAL SECURITY:
- NO email body content in these models
- Only metadata: headers, labels, snippet (first 200 chars)
- Use for in-memory processing only
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


class EmailMetadata(BaseModel):
    """
    Email metadata extracted from Gmail API.

    Contains only metadata and snippet - NO full body content.

    Used for:
    - Classification (Tier 1 and Tier 2)
    - Storing in email_actions audit log
    - In-memory processing only

    CRITICAL: Never add body, html_body, raw_content, or full_message fields!
    """

    # Gmail identifiers
    message_id: str = Field(..., description="Gmail message ID")
    thread_id: str = Field(..., description="Gmail thread ID")

    # Sender information
    from_address: str = Field(..., description="Sender email address")
    from_name: Optional[str] = Field(None, description="Sender display name")
    from_domain: str = Field(..., description="Sender domain (extracted from email)")

    # Email content (metadata only!)
    subject: Optional[str] = Field(None, description="Email subject line (max 500 chars)")
    snippet: Optional[str] = Field(None, description="First 200 chars of email body (from Gmail API)")

    # Gmail labels and categories
    gmail_labels: List[str] = Field(default_factory=list, description="Gmail label IDs")
    gmail_category: Optional[str] = Field(None, description="Gmail category: promotional, social, updates, forums, personal")

    # Extracted headers (only specific headers, not all)
    headers: Dict[str, str] = Field(default_factory=dict, description="Relevant email headers")

    # Timestamps
    received_at: datetime = Field(..., description="When email was received (from internalDate)")

    @validator("subject")
    def truncate_subject(cls, v):
        """Truncate subject to 500 characters max."""
        if v and len(v) > 500:
            return v[:500]
        return v

    @validator("snippet")
    def truncate_snippet(cls, v):
        """Truncate snippet to 200 characters max."""
        if v and len(v) > 200:
            return v[:200]
        return v

    @validator("from_domain")
    def validate_domain(cls, v):
        """Ensure domain is lowercase."""
        return v.lower() if v else v

    def has_label(self, label: str) -> bool:
        """
        Check if email has a specific Gmail label.

        Args:
            label: Label ID (e.g., 'STARRED', 'CATEGORY_PROMOTIONS')

        Returns:
            True if email has the label
        """
        return label in self.gmail_labels

    def has_header(self, header_name: str) -> bool:
        """
        Check if email has a specific header.

        Args:
            header_name: Header name (case-insensitive)

        Returns:
            True if header exists
        """
        return header_name.lower() in {k.lower(): v for k, v in self.headers.items()}

    def get_header(self, header_name: str) -> Optional[str]:
        """
        Get header value by name (case-insensitive).

        Args:
            header_name: Header name

        Returns:
            Header value or None if not found
        """
        headers_lower = {k.lower(): v for k, v in self.headers.items()}
        return headers_lower.get(header_name.lower())

    @property
    def is_starred(self) -> bool:
        """Check if email is starred by user."""
        return self.has_label("STARRED")

    @property
    def is_important(self) -> bool:
        """Check if email is marked important by Gmail."""
        return self.has_label("IMPORTANT")

    @property
    def is_promotional(self) -> bool:
        """Check if email is in promotional category."""
        return self.has_label("CATEGORY_PROMOTIONS")

    @property
    def is_social(self) -> bool:
        """Check if email is in social category."""
        return self.has_label("CATEGORY_SOCIAL")

    @property
    def is_updates(self) -> bool:
        """Check if email is in updates category."""
        return self.has_label("CATEGORY_UPDATES")

    @property
    def is_forums(self) -> bool:
        """Check if email is in forums category."""
        return self.has_label("CATEGORY_FORUMS")

    @property
    def is_personal(self) -> bool:
        """Check if email is in personal category (or no category)."""
        return (
            self.has_label("CATEGORY_PERSONAL") or
            self.gmail_category == "personal" or
            not any([self.is_promotional, self.is_social, self.is_updates, self.is_forums])
        )

    @property
    def has_unsubscribe_header(self) -> bool:
        """Check if email has List-Unsubscribe header (indicates marketing email)."""
        return self.has_header("List-Unsubscribe")

    @property
    def is_bulk_mail(self) -> bool:
        """Check if email has bulk mail headers."""
        return (
            self.get_header("Precedence") == "bulk" or
            self.get_header("Auto-Submitted") == "auto-generated"
        )

    class Config:
        schema_extra = {
            "example": {
                "message_id": "18c3f2a1b2c3d4e5",
                "thread_id": "18c3f2a1b2c3d4e5",
                "from_address": "deals@oldnavy.com",
                "from_name": "Old Navy",
                "from_domain": "oldnavy.com",
                "subject": "50% Off Everything - Today Only!",
                "snippet": "Don't miss out on our biggest sale of the year! Shop now and save 50% on all items...",
                "gmail_labels": ["INBOX", "CATEGORY_PROMOTIONS", "UNREAD"],
                "gmail_category": "promotional",
                "headers": {
                    "List-Unsubscribe": "<mailto:unsubscribe@oldnavy.com>",
                    "Precedence": "bulk",
                    "X-Mailer": "Mailchimp"
                },
                "received_at": "2025-11-04T12:34:56Z"
            }
        }


class EmailMetadataExtractError(Exception):
    """
    Exception raised when email metadata extraction fails.

    Used to distinguish extraction errors from other errors.
    """
    pass
