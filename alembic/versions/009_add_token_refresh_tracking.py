"""Add token refresh tracking to mailboxes table

Revision ID: 009
Revises: 008
Create Date: 2025-11-17

PRD-0007: Token Refresh Resilience
Adds columns to track OAuth token refresh failures and retry attempts.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add token refresh tracking columns to mailboxes table."""

    # Add columns
    op.add_column('mailboxes', sa.Column('token_refresh_failed_at', sa.TIMESTAMP(timezone=True), nullable=True))
    op.add_column('mailboxes', sa.Column('token_refresh_error', sa.Text(), nullable=True))
    op.add_column('mailboxes', sa.Column('token_refresh_attempt_count', sa.Integer(), server_default='0', nullable=False))

    # Add partial index for failed mailboxes (for monitoring queries)
    op.create_index(
        'idx_mailboxes_token_refresh_failed',
        'mailboxes',
        ['token_refresh_failed_at'],
        unique=False,
        postgresql_where=sa.text('token_refresh_failed_at IS NOT NULL')
    )


def downgrade() -> None:
    """Remove token refresh tracking columns from mailboxes table."""

    # Drop index first
    op.drop_index('idx_mailboxes_token_refresh_failed', table_name='mailboxes')

    # Drop columns
    op.drop_column('mailboxes', 'token_refresh_attempt_count')
    op.drop_column('mailboxes', 'token_refresh_error')
    op.drop_column('mailboxes', 'token_refresh_failed_at')
