"""
UserSettings model - per-user configuration and preferences.
"""

from sqlalchemy import Column, Float, String, Boolean, ForeignKey, ARRAY, Integer, Date
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import date

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

    # Usage tracking and billing
    plan_tier = Column(String, default="starter", nullable=False)  # 'starter' | 'pro' | 'business'
    monthly_email_limit = Column(Integer, default=10000, nullable=False)  # Emails per month
    emails_processed_this_month = Column(Integer, default=0, nullable=False)  # Counter
    ai_cost_this_month = Column(Float, default=0.0, nullable=False)  # OpenAI API cost tracking
    current_billing_period_start = Column(Date, default=date.today, nullable=False)  # Reset monthly

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings user_id={self.user_id}>"

    @property
    def is_sandbox_mode(self) -> bool:
        """Check if user is in sandbox mode (no real actions)."""
        return not self.action_mode_enabled

    @property
    def has_reached_monthly_limit(self) -> bool:
        """Check if user has reached their monthly email processing limit."""
        if self.monthly_email_limit == 0:
            return False  # Zero limit = no limit (unlimited)
        return self.emails_processed_this_month >= self.monthly_email_limit

    @property
    def emails_remaining_this_month(self) -> int:
        """Calculate how many emails user can still process this month."""
        return max(0, self.monthly_email_limit - self.emails_processed_this_month)

    @property
    def usage_percentage(self) -> float:
        """Calculate usage as percentage of monthly limit."""
        if self.monthly_email_limit == 0:
            return 0.0
        return min(100.0, (self.emails_processed_this_month / self.monthly_email_limit) * 100)

    @property
    def is_approaching_limit(self) -> bool:
        """Check if user has used 80%+ of their monthly limit."""
        return self.usage_percentage >= 80.0

    def get_limit_for_tier(self, tier: str) -> int:
        """Get email limit for a given plan tier."""
        tier_limits = {
            "starter": 10000,
            "pro": 25000,
            "business": 100000,
        }
        return tier_limits.get(tier, 10000)
