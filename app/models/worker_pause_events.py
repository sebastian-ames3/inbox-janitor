"""
WorkerPauseEvent model - tracks classification worker pause events.

Records when the WORKER_PAUSED environment variable causes emails to skip
classification, enabling monitoring and alerting.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base


class WorkerPauseEvent(Base):
    """
    Worker pause event record for operational monitoring.

    Tracks when classification worker is paused via WORKER_PAUSED=true.
    Used to:
    - Alert admin if paused >5 minutes
    - Track how many emails were skipped during pause
    - Resume processing when pause lifted
    """

    __tablename__ = "worker_pause_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mailbox_id = Column(UUID(as_uuid=True), ForeignKey("mailboxes.id"), nullable=True, index=True)
    message_id = Column(String, nullable=True)  # Gmail message ID that was skipped
    paused_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resumed_at = Column(DateTime, nullable=True)
    skipped_count = Column(Integer, default=0, nullable=False)  # Number of emails skipped

    # Relationships
    mailbox = relationship("Mailbox")

    def __repr__(self):
        status = "resumed" if self.resumed_at else "paused"
        return f"<WorkerPauseEvent {status} at {self.paused_at}, skipped={self.skipped_count}>"

    @property
    def is_active(self) -> bool:
        """Check if this pause event is still active (not resumed)."""
        return self.resumed_at is None

    @property
    def duration_seconds(self) -> float:
        """Calculate pause duration in seconds."""
        end_time = self.resumed_at or datetime.utcnow()
        duration = end_time - self.paused_at
        return duration.total_seconds()
