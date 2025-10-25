"""
Core application configuration using Pydantic Settings.

All environment variables are loaded here and validated.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    # App Configuration
    APP_NAME: str = "Inbox Janitor"
    APP_URL: str = "http://localhost:8000"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str

    # Security & Encryption
    SECRET_KEY: str  # For JWT signing
    ENCRYPTION_KEY: str  # For Fernet token encryption (44-char base64)

    # OAuth - Google
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # OAuth - Microsoft 365 (V1)
    MICROSOFT_CLIENT_ID: Optional[str] = None
    MICROSOFT_CLIENT_SECRET: Optional[str] = None
    MICROSOFT_REDIRECT_URI: Optional[str] = None

    # OpenAI API
    OPENAI_API_KEY: str

    # Postmark Email
    POSTMARK_API_KEY: str
    POSTMARK_FROM_EMAIL: str = "noreply@inboxjanitor.com"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # Google Cloud Pub/Sub (for Gmail webhooks)
    GOOGLE_PROJECT_ID: Optional[str] = None
    GOOGLE_PUBSUB_TOPIC: Optional[str] = None
    GOOGLE_PUBSUB_SUBSCRIPTION: Optional[str] = None

    # Stripe (Week 6+)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None

    # Sentry Monitoring
    SENTRY_DSN: Optional[str] = None

    # Rate Limiting
    RATE_LIMIT_EMAILS_PER_MIN: int = 10  # Gmail API quota safety

    # Classification Thresholds
    DEFAULT_AUTO_THRESHOLD: float = 0.85  # Auto-act if confidence >= this
    DEFAULT_REVIEW_THRESHOLD: float = 0.55  # Review mode if between this and auto

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set Celery URLs to Redis if not explicitly set
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL
        # Set Google redirect URI if not set
        if not self.GOOGLE_REDIRECT_URI:
            self.GOOGLE_REDIRECT_URI = f"{self.APP_URL}/auth/google/callback"

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def database_url_sync(self) -> str:
        """Get synchronous database URL (for Alembic migrations)."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


# Global settings instance
settings = Settings()
