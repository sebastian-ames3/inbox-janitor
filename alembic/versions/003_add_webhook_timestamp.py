"""Add last_webhook_received_at to mailboxes

Revision ID: 003
Revises: 002
Create Date: 2025-11-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add last_webhook_received_at column to mailboxes table."""
    op.add_column('mailboxes', sa.Column('last_webhook_received_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove last_webhook_received_at column from mailboxes table."""
    op.drop_column('mailboxes', 'last_webhook_received_at')
