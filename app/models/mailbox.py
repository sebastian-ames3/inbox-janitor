"""
Mailbox model - represents connected email accounts (OAuth connections).

Each mailbox stores encrypted OAuth tokens and Gmail watch state.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from sqlalchemy.orm import relationship

from app.core.database import Base


class Mailbox(Base):
    """
    Connected email account (Gmail or Microsoft 365).

    CRITICAL SECURITY:
    - access_token and refresh_token are ALWAYS encrypted before storage
    - Tokens are NEVER logged
    - Use app.core.security.decrypt_token() to decrypt for API calls
    """

    __tablename__ = "mailboxes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Provider info
    provider = Column(String, nullable=False)  # 'gmail' | 'microsoft365'
    email_address = Column(String, nullable=False, index=True)

    # Encrypted OAuth tokens (NEVER store plaintext!)
    encrypted_access_token = Column(Text, nullable=False)
    encrypted_refresh_token = Column(Text, nullable=False)
    token_expires_at = Column(DateTime, nullable=True)

    # Gmail watch state (for delta sync)
    watch_expiration = Column(DateTime, nullable=True)  # Gmail watch expires in 7 days
    last_history_id = Column(String, nullable=True)  # Gmail history ID for incremental sync

    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    last_webhook_received_at = Column(DateTime, nullable=True)  # Track webhook delivery for fallback polling
    last_used_at = Column(DateTime, default=datetime.utcnow, nullable=True)  # Track user activity

    # Token refresh tracking (PRD-0007: Token Refresh Resilience)
    token_refresh_failed_at = Column(TIMESTAMP(timezone=True), nullable=True)  # When last token refresh failed
    token_refresh_error = Column(Text, nullable=True)  # Error message from last failed refresh
    token_refresh_attempt_count = Column(Integer, default=0, nullable=False)  # Number of consecutive failed attempts

    # Relationships
    user = relationship("User", back_populates="mailboxes")
    email_actions = relationship("EmailAction", back_populates="mailbox", cascade="all, delete-orphan")
    email_metadata = relationship("EmailMetadataDB", back_populates="mailbox", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Mailbox {self.provider}:{self.email_address}>"

    @property
    def needs_watch_renewal(self) -> bool:
        """Check if Gmail watch needs renewal (renew 1 day before expiry)."""
        if not self.watch_expiration or self.provider != "gmail":
            return False
        from datetime import timedelta
        renewal_threshold = datetime.utcnow() + timedelta(days=1)
        return self.watch_expiration < renewal_threshold
