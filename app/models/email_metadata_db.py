"""
Email metadata database model (SQLAlchemy).

CRITICAL SECURITY:
- NO body, html_body, raw_content, or full_message columns
- Only metadata and snippet (first 200 chars)
- Database trigger prevents adding body-related columns

This is separate from the Pydantic EmailMetadata model in app/models/email_metadata.py.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


class EmailMetadataDB(Base):
    """
    Email metadata database model.

    Stores metadata extracted from Gmail API for:
    - Classification (Tier 1 and Tier 2)
    - Audit trail
    - Learning and improvement

    CRITICAL SECURITY:
    - NEVER add body, html_body, raw_content, or full_message columns
    - Only stores metadata and snippet (first 200 chars)
    - PostgreSQL trigger prevents adding body-related columns
    """

    __tablename__ = "email_metadata"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Foreign keys
    mailbox_id = Column(
        UUID(as_uuid=True),
        ForeignKey("mailboxes.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Gmail identifiers
    message_id = Column(String, nullable=False, index=True)  # Gmail message ID
    thread_id = Column(String, nullable=True, index=True)  # Gmail thread ID

    # Sender information
    from_address = Column(String, nullable=False, index=True)
    from_name = Column(String(200), nullable=True)
    from_domain = Column(String, nullable=False, index=True)

    # Email content (metadata only - NO BODY!)
    subject = Column(String(500), nullable=True)  # Subject line (max 500 chars)
    snippet = Column(String(200), nullable=True)  # First 200 chars only!

    # Gmail labels and categories
    gmail_labels = Column(JSONB, nullable=True, default=list)  # Array of label IDs
    gmail_category = Column(String, nullable=True, index=True)  # promotional, social, updates, forums, personal

    # Extracted headers (only relevant headers, not all)
    headers = Column(JSONB, nullable=True, default=dict)  # Dict of relevant headers

    # Timestamps
    received_at = Column(DateTime, nullable=False, index=True)  # When email was received
    processed_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When we processed it
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    mailbox = relationship("Mailbox", back_populates="email_metadata")

    def __repr__(self):
        return f"<EmailMetadataDB {self.message_id} from {self.from_address}>"

    # Table arguments (indexes and constraints)
    __table_args__ = (
        # Unique constraint: one metadata record per message per mailbox
        Index(
            "idx_email_metadata_mailbox_message",
            "mailbox_id",
            "message_id",
            unique=True
        ),
        # Index for cleanup queries (processed_at)
        Index("idx_email_metadata_processed_at", "processed_at"),
        # Composite index for mailbox + created_at (common query pattern)
        Index("idx_email_metadata_mailbox_created", "mailbox_id", "created_at"),
        # Index for domain analysis
        Index("idx_email_metadata_from_domain", "from_domain"),
        # Index for category analysis
        Index("idx_email_metadata_category", "gmail_category"),
    )
