"""
Database models package.

Import all models here so Alembic can discover them for migrations.
"""

from app.models.user import User
from app.models.mailbox import Mailbox
from app.models.email_action import EmailAction
from app.models.user_settings import UserSettings
from app.models.sender_stats import SenderStats
from app.models.email_metadata_db import EmailMetadataDB

__all__ = [
    "User",
    "Mailbox",
    "EmailAction",
    "UserSettings",
    "SenderStats",
    "EmailMetadataDB",
]
