"""Pydantic models for digest email data."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class EmailAction(BaseModel):
    """Single email action for digest display."""

    from_address: str
    subject: str
    snippet: Optional[str] = None
    action: str  # 'archive' | 'trash' | 'keep' | 'review'
    confidence: float
    created_at: datetime
    message_id: str  # Gmail message ID
    undo_link: Optional[str] = None  # Magic link to undo


class DigestData(BaseModel):
    """Data for weekly digest email.

    Contains summary of actions taken in the past week and
    items needing review.
    """

    user_email: EmailStr
    user_name: Optional[str] = None
    period_start: datetime
    period_end: datetime

    # Summary counts
    total_processed: int = 0
    archived_count: int = 0
    trashed_count: int = 0
    kept_count: int = 0

    # Items for review (borderline cases, low confidence)
    review_items: List[EmailAction] = Field(default_factory=list)

    # Top senders that were cleaned up
    top_cleaned_senders: List[dict] = Field(default_factory=list)  # [{'sender': 'promo@store.com', 'count': 42}]

    # Settings
    action_mode_enabled: bool = False
    dashboard_link: str  # Link to settings dashboard
    audit_link: str  # Link to audit log


class DailySummaryData(BaseModel):
    """Data for daily summary email (optional, power users only)."""

    user_email: EmailStr
    date: datetime

    processed_count: int = 0
    archived_count: int = 0
    trashed_count: int = 0

    # Quick stats
    top_sender_cleaned: Optional[str] = None  # Most frequently cleaned sender
    total_time_saved: Optional[int] = None  # Estimated minutes saved (placeholder)

    dashboard_link: str


class BacklogData(BaseModel):
    """Data for backlog analysis email (one-time cleanup offer)."""

    user_email: EmailStr
    analysis_date: datetime

    # Backlog summary
    total_old_emails: int  # Emails older than 30 days
    promotional_count: int
    social_count: int
    estimated_cleanup_time: int  # Minutes (manually reviewing all)
    estimated_cleanup_size: int  # MB

    # Breakdown by category
    category_breakdown: List[dict] = Field(default_factory=list)  # [{'category': 'Promotions', 'count': 5200}]

    # Magic link to initiate backlog cleanup
    cleanup_link: str

    # Settings
    dashboard_link: str


class ActionReceiptData(BaseModel):
    """Data for action receipt email (confirmation after user action via magic link)."""

    user_email: EmailStr
    action_type: str  # 'undo' | 'backlog_cleanup' | 'enable_action_mode'
    timestamp: datetime

    # Details
    affected_count: Optional[int] = None  # Number of emails affected
    success: bool = True
    message: str  # User-facing message

    dashboard_link: str


class WelcomeEmailData(BaseModel):
    """Data for welcome email (sent after OAuth connection)."""

    user_email: EmailStr
    connected_email: str  # Gmail address connected
    connection_date: datetime

    # Links
    dashboard_link: str
    audit_link: str
    help_link: Optional[str] = None

    # Settings
    sandbox_mode_enabled: bool = True  # Always True for new users
