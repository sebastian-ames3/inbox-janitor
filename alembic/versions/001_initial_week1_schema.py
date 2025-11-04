"""Initial Week 1 schema: users, mailboxes, email_actions, settings

Revision ID: 001
Revises:
Create Date: 2025-11-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create mailboxes table
    op.create_table(
        'mailboxes',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('email_address', sa.String(), nullable=False),
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=False),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('watch_expiration', sa.DateTime(), nullable=True),
        sa.Column('last_history_id', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mailboxes_email_address'), 'mailboxes', ['email_address'], unique=False)
    op.create_index(op.f('ix_mailboxes_user_id'), 'mailboxes', ['user_id'], unique=False)

    # Create email_actions table
    op.create_table(
        'email_actions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mailbox_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('message_id', sa.String(), nullable=False),
        sa.Column('thread_id', sa.String(), nullable=True),
        sa.Column('from_address', sa.String(), nullable=True),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('snippet', sa.String(length=200), nullable=True),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('classification_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('undone_at', sa.DateTime(), nullable=True),
        sa.Column('can_undo_until', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['mailbox_id'], ['mailboxes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_email_actions_action'), 'email_actions', ['action'], unique=False)
    op.create_index(op.f('ix_email_actions_can_undo_until'), 'email_actions', ['can_undo_until'], unique=False)
    op.create_index(op.f('ix_email_actions_created_at'), 'email_actions', ['created_at'], unique=False)
    op.create_index(op.f('ix_email_actions_from_address'), 'email_actions', ['from_address'], unique=False)
    op.create_index(op.f('ix_email_actions_mailbox_id'), 'email_actions', ['mailbox_id'], unique=False)
    op.create_index(op.f('ix_email_actions_message_id'), 'email_actions', ['message_id'], unique=False)
    op.create_index(op.f('ix_email_actions_thread_id'), 'email_actions', ['thread_id'], unique=False)

    # Create immutability trigger for email_actions
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_email_action_modification()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION 'email_actions table is append-only (immutable audit log)';
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER email_actions_immutable
        BEFORE UPDATE OR DELETE ON email_actions
        FOR EACH ROW EXECUTE FUNCTION prevent_email_action_modification();
    """)

    # Create user_settings table
    op.create_table(
        'user_settings',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('confidence_auto_threshold', sa.Float(), nullable=False),
        sa.Column('confidence_review_threshold', sa.Float(), nullable=False),
        sa.Column('digest_schedule', sa.String(), nullable=False),
        sa.Column('digest_day_of_week', sa.String(), nullable=True),
        sa.Column('digest_hour', sa.String(), nullable=True),
        sa.Column('action_mode_enabled', sa.Boolean(), nullable=False),
        sa.Column('auto_trash_promotions', sa.Boolean(), nullable=False),
        sa.Column('auto_trash_social', sa.Boolean(), nullable=False),
        sa.Column('keep_receipts', sa.Boolean(), nullable=False),
        sa.Column('blocked_senders', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('allowed_domains', postgresql.ARRAY(sa.String()), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )

    # Create sender_stats table
    op.create_table(
        'sender_stats',
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('sender_address', sa.String(), nullable=False),
        sa.Column('total_received', sa.Integer(), nullable=False),
        sa.Column('opened_count', sa.Integer(), nullable=False),
        sa.Column('replied_count', sa.Integer(), nullable=False),
        sa.Column('trashed_count', sa.Integer(), nullable=False),
        sa.Column('undone_count', sa.Integer(), nullable=False),
        sa.Column('last_received_at', sa.DateTime(), nullable=True),
        sa.Column('last_opened_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'sender_address')
    )
    op.create_index(op.f('ix_sender_stats_sender_address'), 'sender_stats', ['sender_address'], unique=False)
    op.create_index(op.f('ix_sender_stats_user_id'), 'sender_stats', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop all tables."""

    # Drop tables in reverse order (handle foreign keys)
    op.drop_index(op.f('ix_sender_stats_user_id'), table_name='sender_stats')
    op.drop_index(op.f('ix_sender_stats_sender_address'), table_name='sender_stats')
    op.drop_table('sender_stats')

    op.drop_table('user_settings')

    # Drop email_actions trigger and table
    op.execute("DROP TRIGGER IF EXISTS email_actions_immutable ON email_actions;")
    op.execute("DROP FUNCTION IF EXISTS prevent_email_action_modification();")
    op.drop_index(op.f('ix_email_actions_thread_id'), table_name='email_actions')
    op.drop_index(op.f('ix_email_actions_message_id'), table_name='email_actions')
    op.drop_index(op.f('ix_email_actions_mailbox_id'), table_name='email_actions')
    op.drop_index(op.f('ix_email_actions_from_address'), table_name='email_actions')
    op.drop_index(op.f('ix_email_actions_created_at'), table_name='email_actions')
    op.drop_index(op.f('ix_email_actions_can_undo_until'), table_name='email_actions')
    op.drop_index(op.f('ix_email_actions_action'), table_name='email_actions')
    op.drop_table('email_actions')

    op.drop_index(op.f('ix_mailboxes_user_id'), table_name='mailboxes')
    op.drop_index(op.f('ix_mailboxes_email_address'), table_name='mailboxes')
    op.drop_table('mailboxes')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
