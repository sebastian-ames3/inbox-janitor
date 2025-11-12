"""clear_polluted_email_actions

Revision ID: 007
Revises: 006
Create Date: 2025-11-12

Clears all polluted email_actions data classified with old thresholds.
Temporarily drops immutability trigger, truncates table, then recreates trigger.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '007'
down_revision = '006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Clear polluted classification data."""
    # Drop immutability trigger
    op.execute("""
        DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;
    """)

    # Clear all data
    op.execute("TRUNCATE email_actions;")

    # Recreate immutability trigger
    op.execute("""
        CREATE TRIGGER email_actions_immutable
        BEFORE UPDATE OR DELETE ON email_actions
        FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
    """)


def downgrade() -> None:
    """No downgrade - data is cleared intentionally."""
    pass
