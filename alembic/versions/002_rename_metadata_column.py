"""Rename metadata column to classification_metadata in email_actions

Revision ID: 002
Revises: 001
Create Date: 2025-11-04

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename metadata column to classification_metadata to avoid SQLAlchemy reserved name conflict."""

    # Temporarily drop the immutability trigger
    op.execute("DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;")

    # Rename the column
    op.alter_column(
        'email_actions',
        'metadata',
        new_column_name='classification_metadata',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True
    )

    # Recreate the immutability trigger
    op.execute("""
        CREATE TRIGGER email_actions_immutable
        BEFORE UPDATE OR DELETE ON email_actions
        FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
    """)


def downgrade() -> None:
    """Revert classification_metadata column back to metadata."""

    # Temporarily drop the immutability trigger
    op.execute("DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;")

    # Rename the column back
    op.alter_column(
        'email_actions',
        'classification_metadata',
        new_column_name='metadata',
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        existing_nullable=True
    )

    # Recreate the immutability trigger
    op.execute("""
        CREATE TRIGGER email_actions_immutable
        BEFORE UPDATE OR DELETE ON email_actions
        FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
    """)
