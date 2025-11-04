"""
Classification models for email categorization.

These models represent classification results from Tier 1 (metadata-based)
and future Tier 2 (AI-based) classifiers.
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ClassificationAction(str, Enum):
    """
    Actions that can be taken on an email.

    - KEEP: Keep in inbox (important)
    - ARCHIVE: Archive (future value, like receipts)
    - TRASH: Move to trash (spam/promotional)
    - REVIEW: Needs human review (uncertain)
    """
    KEEP = "keep"
    ARCHIVE = "archive"
    TRASH = "trash"
    REVIEW = "review"


class ClassificationSignal(BaseModel):
    """
    Individual classification signal.

    Represents one factor that contributes to the overall classification.

    Example:
        Signal(name="gmail_category", score=0.60, reason="CATEGORY_PROMOTIONS")
    """
    name: str = Field(..., description="Signal name (e.g., 'gmail_category', 'list_unsubscribe')")
    score: float = Field(..., description="Signal contribution to confidence (-1.0 to 1.0)")
    reason: Optional[str] = Field(None, description="Human-readable explanation")

    def __repr__(self):
        return f"<Signal {self.name}={self.score:.2f}>"

    class Config:
        schema_extra = {
            "example": {
                "name": "gmail_category",
                "score": 0.60,
                "reason": "Email in CATEGORY_PROMOTIONS"
            }
        }


class ClassificationResult(BaseModel):
    """
    Complete classification result for an email.

    Contains:
    - Final action recommendation
    - Confidence score (0.0-1.0)
    - All signals that contributed
    - Human-readable explanation

    Used for:
    - Storing in email_actions audit log
    - Decision making (action vs review)
    - Learning and improvement
    """
    action: ClassificationAction = Field(..., description="Recommended action")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)", ge=0.0, le=1.0)
    signals: List[ClassificationSignal] = Field(default_factory=list, description="Contributing signals")
    reason: str = Field(..., description="Human-readable explanation")
    overridden: bool = Field(False, description="Whether safety rails overrode the classification")
    override_reason: Optional[str] = Field(None, description="Why classification was overridden")

    @property
    def total_signal_score(self) -> float:
        """Calculate total score from all signals."""
        return sum(signal.score for signal in self.signals)

    @property
    def signal_count(self) -> int:
        """Count of signals that contributed."""
        return len(self.signals)

    @property
    def should_take_action(self) -> bool:
        """
        Determine if action should be taken automatically.

        Only auto-act if:
        - Confidence >= 0.85 (high confidence)
        - Not overridden by safety rails
        - Action is TRASH or ARCHIVE (never auto-KEEP)
        """
        return (
            self.confidence >= 0.85 and
            not self.overridden and
            self.action in [ClassificationAction.TRASH, ClassificationAction.ARCHIVE]
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dict for database storage.

        Returns dict suitable for JSONB column.
        """
        return {
            "action": self.action.value,
            "confidence": self.confidence,
            "signals": [
                {"name": s.name, "score": s.score, "reason": s.reason}
                for s in self.signals
            ],
            "reason": self.reason,
            "overridden": self.overridden,
            "override_reason": self.override_reason,
        }

    class Config:
        schema_extra = {
            "example": {
                "action": "trash",
                "confidence": 0.95,
                "signals": [
                    {"name": "gmail_category", "score": 0.60, "reason": "CATEGORY_PROMOTIONS"},
                    {"name": "list_unsubscribe", "score": 0.40, "reason": "Has List-Unsubscribe header"},
                    {"name": "sender_domain", "score": 0.45, "reason": "Marketing platform: sendgrid.net"}
                ],
                "reason": "Promotional email from marketing platform with unsubscribe link",
                "overridden": False,
                "override_reason": None
            }
        }


class ClassificationTier(str, Enum):
    """
    Classification tier used.

    - TIER_1: Metadata-based (Gmail category, headers, sender analysis)
    - TIER_2: AI-based (GPT-4o-mini with enhanced prompt)
    - TIER_3: User rules (manual allow/block lists)
    """
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    TIER_3 = "tier_3"


class ClassificationMetadata(BaseModel):
    """
    Metadata about the classification process.

    Used for logging, learning, and debugging.
    """
    tier: ClassificationTier = Field(..., description="Which tier classified this email")
    processing_time_ms: Optional[float] = Field(None, description="Time taken to classify (milliseconds)")
    model_used: Optional[str] = Field(None, description="AI model used (if Tier 2)")
    cost: Optional[float] = Field(None, description="API cost (if Tier 2)")
    version: str = Field("1.0", description="Classifier version")

    class Config:
        schema_extra = {
            "example": {
                "tier": "tier_1",
                "processing_time_ms": 15.3,
                "model_used": None,
                "cost": None,
                "version": "1.0"
            }
        }


class SafetyOverride(BaseModel):
    """
    Safety override information.

    When safety rails prevent an action, this captures why.
    """
    triggered_by: str = Field(..., description="What triggered the override (e.g., 'starred', 'keyword:receipt')")
    original_action: ClassificationAction = Field(..., description="What action was originally recommended")
    new_action: ClassificationAction = Field(..., description="Action after override")
    reason: str = Field(..., description="Human-readable explanation")

    class Config:
        schema_extra = {
            "example": {
                "triggered_by": "keyword:receipt",
                "original_action": "trash",
                "new_action": "keep",
                "reason": "Contains exception keyword 'receipt' - keeping for safety"
            }
        }
