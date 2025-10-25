"""
SenderStats model - learning from user behavior with specific senders.

Used to improve classification accuracy over time.
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SenderStats(Base):
    """
    Per-user statistics about email senders.

    Used for learning:
    - If user never opens emails from sender X → likely trash
    - If user always replies to sender Y → likely keep
    - If user hasn't received from sender Z in 90 days → stale

    Retention: 90 days (rolling window)
    """

    __tablename__ = "sender_stats"
    __table_args__ = (
        PrimaryKeyConstraint("user_id", "sender_address"),
    )

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    sender_address = Column(String, nullable=False, index=True)

    # Behavior metrics
    total_received = Column(Integer, default=0, nullable=False)
    opened_count = Column(Integer, default=0, nullable=False)  # Future: Gmail API read detection
    replied_count = Column(Integer, default=0, nullable=False)  # Future: sent mail analysis
    trashed_count = Column(Integer, default=0, nullable=False)  # How often user trashed this sender
    undone_count = Column(Integer, default=0, nullable=False)  # How often user undid our actions

    # Timestamps
    last_received_at = Column(DateTime, nullable=True)
    last_opened_at = Column(DateTime, nullable=True)  # Future feature
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SenderStats {self.sender_address} received={self.total_received}>"

    @property
    def open_rate(self) -> float:
        """Calculate open rate (0.0-1.0). Future feature."""
        if self.total_received == 0:
            return 0.0
        return self.opened_count / self.total_received

    @property
    def reply_rate(self) -> float:
        """Calculate reply rate (0.0-1.0). Future feature."""
        if self.total_received == 0:
            return 0.0
        return self.replied_count / self.total_received

    @property
    def trash_rate(self) -> float:
        """Calculate user's trash rate for this sender (0.0-1.0)."""
        if self.total_received == 0:
            return 0.0
        return self.trashed_count / self.total_received

    @property
    def undo_rate(self) -> float:
        """Calculate undo rate (high = we're misclassifying this sender)."""
        actions_taken = self.trashed_count + self.opened_count
        if actions_taken == 0:
            return 0.0
        return self.undone_count / actions_taken
