"""
UserSettings model - per-user configuration and preferences.
"""

from sqlalchemy import Column, Float, String, Boolean, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserSettings(Base):
    """
    User preferences and configuration.

    Defaults are conservative (high confidence thresholds, safe behaviors).
    """

    __tablename__ = "user_settings"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)

    # Classification thresholds
    confidence_auto_threshold = Column(Float, default=0.85, nullable=False)  # Auto-act if >= this
    confidence_review_threshold = Column(Float, default=0.55, nullable=False)  # Review if between thresholds

    # Digest configuration
    digest_schedule = Column(String, default="weekly", nullable=False)  # 'daily' | 'weekly' | 'off'
    digest_day_of_week = Column(String, default="sunday", nullable=True)  # For weekly digest
    digest_hour = Column(String, default="09:00", nullable=True)  # User's timezone

    # Action mode (sandbox vs live)
    action_mode_enabled = Column(Boolean, default=False, nullable=False)  # False = sandbox (dry-run)

    # Auto-action preferences
    auto_trash_promotions = Column(Boolean, default=True, nullable=False)
    auto_trash_social = Column(Boolean, default=True, nullable=False)
    keep_receipts = Column(Boolean, default=True, nullable=False)  # Never trash receipts/invoices

    # User rules (block/allow lists)
    blocked_senders = Column(ARRAY(String), default=[], nullable=False)  # Always trash
    allowed_domains = Column(ARRAY(String), default=[], nullable=False)  # Always keep (e.g., @work.com)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"

    @property
    def is_sandbox_mode(self) -> bool:
        """Check if user is in sandbox mode (no real actions)."""
        return not self.action_mode_enabled
