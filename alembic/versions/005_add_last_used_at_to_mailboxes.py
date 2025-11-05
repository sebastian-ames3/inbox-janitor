"""Add last_used_at to mailboxes table

Revision ID: 005
Revises: 004
Create Date: 2025-11-05

"""
from datetime import datetime, timezone
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_used_at column to mailboxes table."""

    op.add_column('mailboxes', sa.Column('last_used_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove last_used_at column from mailboxes table."""

    op.drop_column('mailboxes', 'last_used_at')
