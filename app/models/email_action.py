"""
EmailAction model - immutable audit log of all email actions.

CRITICAL: This table is append-only (immutable). Updates/deletes are blocked by DB trigger.
"""

import uuid
from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class EmailAction(Base):
    """
    Audit log of email classification and actions.

    CRITICAL SECURITY:
    - NEVER store full email body (only snippet - first 200 chars)
    - This table is IMMUTABLE (enforced by PostgreSQL trigger)
    - Use for audit trail, undo functionality, and learning

    Action Types:
    - 'keep': Email kept in inbox (important)
    - 'archive': Email archived (future value)
    - 'trash': Email moved to trash (spam/promotional)
    - 'review': Uncertain classification (user review needed)
    - 'undo': User undid a previous action
    """

    __tablename__ = "email_actions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id = Column(UUID(as_uuid=True), ForeignKey("mailboxes.id", ondelete="CASCADE"), nullable=False, index=True)

    # Email identifiers
    message_id = Column(String, nullable=False, index=True)  # Gmail message ID
    thread_id = Column(String, nullable=True, index=True)  # Gmail thread ID

    # Metadata (NO FULL BODY!)
    from_address = Column(String, nullable=True, index=True)
    subject = Column(String, nullable=True)
    snippet = Column(String(200), nullable=True)  # First 200 chars only!

    # Classification
    action = Column(String, nullable=False, index=True)  # 'keep' | 'archive' | 'trash' | 'review' | 'undo'
    reason = Column(Text, nullable=True)  # Human-readable explanation
    confidence = Column(Float, nullable=True)  # 0.0-1.0 confidence score

    # Classification metadata (for learning and debugging)
    metadata = Column(JSONB, nullable=True)  # Dict: {gmail_category, has_unsubscribe, sender_open_rate, etc.}

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    undone_at = Column(DateTime, nullable=True)  # If action was undone
    can_undo_until = Column(DateTime, nullable=True, index=True)  # 30 days from action

    # Relationships
    mailbox = relationship("Mailbox", back_populates="email_actions")

    def __repr__(self):
        return f"<EmailAction {self.action} {self.from_address}>"

    @property
    def can_undo(self) -> bool:
        """Check if action can still be undone (within 30-day window)."""
        if self.undone_at or not self.can_undo_until:
            return False
        return datetime.utcnow() < self.can_undo_until

    @staticmethod
    def calculate_undo_deadline() -> datetime:
        """Calculate undo deadline (30 days from now)."""
        return datetime.utcnow() + timedelta(days=30)
