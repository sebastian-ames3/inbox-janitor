"""Create test user for E2E authentication

Revision ID: 004
Revises: 003
Create Date: 2025-11-05

"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create test user and mailbox for E2E testing."""

    # Test user UUID (deterministic for consistency)
    test_user_id = '00000000-0000-0000-0000-000000000001'
    test_mailbox_id = '00000000-0000-0000-0000-000000000002'

    # Get current timestamp
    now = datetime.now(timezone.utc)

    # Insert test user (if not exists)
    op.execute(f"""
        INSERT INTO users (id, email, created_at, is_active)
        VALUES (
            '{test_user_id}',
            'test-user-e2e@inboxjanitor.com',
            '{now.isoformat()}',
            true
        )
        ON CONFLICT (email) DO NOTHING;
    """)

    # Insert test mailbox (if not exists)
    # Using dummy encrypted tokens since this is not a real OAuth connection
    op.execute(f"""
        INSERT INTO mailboxes (
            id,
            user_id,
            provider,
            email_address,
            encrypted_access_token,
            encrypted_refresh_token,
            is_active,
            created_at
        )
        VALUES (
            '{test_mailbox_id}',
            '{test_user_id}',
            'gmail',
            'test-user-e2e@inboxjanitor.com',
            'ENCRYPTED_TEST_ACCESS_TOKEN',
            'ENCRYPTED_TEST_REFRESH_TOKEN',
            false,
            '{now.isoformat()}'
        )
        ON CONFLICT (id) DO NOTHING;
    """)

    # Insert default user settings for test user
    op.execute(f"""
        INSERT INTO user_settings (
            user_id,
            confidence_auto_threshold,
            confidence_review_threshold,
            digest_schedule,
            action_mode_enabled,
            auto_trash_promotions,
            auto_trash_social,
            keep_receipts
        )
        VALUES (
            '{test_user_id}',
            0.85,
            0.55,
            'weekly',
            false,
            true,
            true,
            true
        )
        ON CONFLICT (user_id) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove test user and related data."""

    test_user_id = '00000000-0000-0000-0000-000000000001'

    # Delete in reverse order (due to foreign key constraints)
    op.execute(f"DELETE FROM user_settings WHERE user_id = '{test_user_id}'")
    op.execute(f"DELETE FROM mailboxes WHERE user_id = '{test_user_id}'")
    op.execute(f"DELETE FROM users WHERE id = '{test_user_id}'")
