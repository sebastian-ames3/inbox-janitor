"""Pydantic models for form validation in the portal."""

from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class SettingsUpdate(BaseModel):
    """Model for updating user settings."""

    confidence_auto_threshold: float = Field(
        ge=0.5,
        le=1.0,
        description="Confidence threshold for automatic actions (trash/archive)"
    )
    confidence_review_threshold: float = Field(
        ge=0.5,
        le=1.0,
        description="Confidence threshold for review mode"
    )
    digest_schedule: str = Field(
        pattern="^(daily|weekly|off)$",
        description="Schedule for weekly digest emails"
    )
    action_mode_enabled: bool = Field(
        description="Enable action mode (vs sandbox mode)"
    )
    auto_trash_promotions: bool = Field(
        description="Automatically trash promotional emails"
    )
    auto_trash_social: bool = Field(
        description="Automatically trash social notifications"
    )
    keep_receipts: bool = Field(
        description="Always keep receipts and transactional emails"
    )

    @field_validator('confidence_auto_threshold', 'confidence_review_threshold')
    @classmethod
    def validate_thresholds(cls, v):
        """Ensure thresholds are reasonable."""
        if v < 0.5:
            raise ValueError("Confidence threshold must be at least 0.5 (50%)")
        if v > 1.0:
            raise ValueError("Confidence threshold cannot exceed 1.0 (100%)")
        return v

    @field_validator('confidence_auto_threshold')
    @classmethod
    def validate_auto_threshold(cls, v, info):
        """Ensure auto threshold is higher than review threshold."""
        # Note: This validator runs before we have access to review_threshold
        # We'll need to validate this in the endpoint
        return v


class SettingsToggle(BaseModel):
    """Model for toggling a single setting (HTMX auto-save)."""

    field: str = Field(
        description="Name of the field to toggle"
    )
    value: bool = Field(
        description="New value for the field"
    )

    @field_validator('field')
    @classmethod
    def validate_field(cls, v):
        """Ensure field is a valid boolean setting."""
        allowed_fields = [
            'action_mode_enabled',
            'auto_trash_promotions',
            'auto_trash_social',
            'keep_receipts'
        ]
        if v not in allowed_fields:
            raise ValueError(f"Invalid field. Must be one of: {', '.join(allowed_fields)}")
        return v


class BlockedSenderAdd(BaseModel):
    """Model for adding a blocked sender."""

    email_or_domain: str = Field(
        min_length=3,
        max_length=255,
        description="Email address or domain to block"
    )

    @field_validator('email_or_domain')
    @classmethod
    def validate_email_or_domain(cls, v):
        """Basic validation for email or domain format."""
        v = v.strip().lower()

        # Check for obvious issues
        if ' ' in v:
            raise ValueError("Email or domain cannot contain spaces")

        if '@' in v:
            # Email address format
            if v.count('@') != 1:
                raise ValueError("Invalid email format")
            local, domain = v.split('@')
            if not local or not domain:
                raise ValueError("Invalid email format")
        else:
            # Domain format
            if not '.' in v:
                raise ValueError("Invalid domain format (must include TLD, e.g., example.com)")

        return v


class AllowedDomainAdd(BaseModel):
    """Model for adding an allowed domain."""

    domain: str = Field(
        min_length=3,
        max_length=255,
        pattern=r"^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        description="Domain to allow (e.g., work.com)"
    )

    @field_validator('domain')
    @classmethod
    def validate_domain(cls, v):
        """Validate and normalize domain."""
        v = v.strip().lower()

        # Remove @ prefix if user included it
        if v.startswith('@'):
            v = v[1:]

        return v
