"""
SecurityViolation model - tracks security violations for forensic analysis.

Records critical security events like body content logging or token exposure
with metadata preserved for investigation.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class SecurityViolation(Base):
    """
    Security violation record for forensic tracking.

    Immutable audit log of security events like:
    - Email body content logged to Sentry
    - OAuth tokens exposed in logs
    - Unauthorized access attempts
    - Privacy violations (GDPR)

    All violations trigger immediate admin alerts.
    """

    __tablename__ = "security_violations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    violation_type = Column(String, nullable=False, index=True)  # 'body_content_logged', 'token_exposed', etc.
    severity = Column(String, nullable=False, index=True)  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
    event_metadata = Column(JSONB, nullable=False)  # Forensic data (encrypted at app level if needed)
    description = Column(Text, nullable=True)  # Human-readable description
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<SecurityViolation {self.violation_type} ({self.severity}) at {self.detected_at}>"

    @property
    def is_resolved(self) -> bool:
        """Check if violation has been resolved."""
        return self.resolved_at is not None
