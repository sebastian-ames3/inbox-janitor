"""add usage tracking to user settings

Revision ID: 006
Revises: 005
Create Date: 2025-11-06

Adds usage tracking and billing fields to user_settings table:
- plan_tier: User's subscription tier (starter, pro, business)
- monthly_email_limit: Max emails per month for this tier
- emails_processed_this_month: Counter for current billing period
- ai_cost_this_month: Track OpenAI API costs
- current_billing_period_start: Date when current period started (for resets)

This protects against unprofitable high-volume users and enables
future tiered pricing with overage billing.
"""
from alembic import op
import sqlalchemy as sa
from datetime import date

# revision identifiers, used by Alembic.
revision = '006'
down_revision = '005'
branch_labels = None
depends_on = None


def upgrade():
    """Add usage tracking columns to user_settings table."""

    # Add new columns
    op.add_column('user_settings',
        sa.Column('plan_tier', sa.String(), nullable=False, server_default='starter')
    )

    op.add_column('user_settings',
        sa.Column('monthly_email_limit', sa.Integer(), nullable=False, server_default='10000')
    )

    op.add_column('user_settings',
        sa.Column('emails_processed_this_month', sa.Integer(), nullable=False, server_default='0')
    )

    op.add_column('user_settings',
        sa.Column('ai_cost_this_month', sa.Float(), nullable=False, server_default='0.0')
    )

    op.add_column('user_settings',
        sa.Column('current_billing_period_start', sa.Date(), nullable=False, server_default=sa.text('CURRENT_DATE'))
    )

    # Remove server defaults after columns are created (avoid future default values)
    op.alter_column('user_settings', 'plan_tier', server_default=None)
    op.alter_column('user_settings', 'monthly_email_limit', server_default=None)
    op.alter_column('user_settings', 'emails_processed_this_month', server_default=None)
    op.alter_column('user_settings', 'ai_cost_this_month', server_default=None)
    op.alter_column('user_settings', 'current_billing_period_start', server_default=None)

    # Create index for billing period queries
    op.create_index(
        'ix_user_settings_billing_period',
        'user_settings',
        ['current_billing_period_start'],
        unique=False
    )

    # Create index for plan tier (for analytics queries)
    op.create_index(
        'ix_user_settings_plan_tier',
        'user_settings',
        ['plan_tier'],
        unique=False
    )


def downgrade():
    """Remove usage tracking columns from user_settings table."""

    # Drop indexes
    op.drop_index('ix_user_settings_plan_tier', table_name='user_settings')
    op.drop_index('ix_user_settings_billing_period', table_name='user_settings')

    # Drop columns
    op.drop_column('user_settings', 'current_billing_period_start')
    op.drop_column('user_settings', 'ai_cost_this_month')
    op.drop_column('user_settings', 'emails_processed_this_month')
    op.drop_column('user_settings', 'monthly_email_limit')
    op.drop_column('user_settings', 'plan_tier')
