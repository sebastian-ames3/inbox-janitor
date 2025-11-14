"""add security monitoring tables

Revision ID: 008
Revises: 007
Create Date: 2025-11-14

Adds two tables for security and operational monitoring:

1. security_violations - Forensic tracking of security events
   - Logs critical events like body content logging, token exposure
   - Immutable audit trail for GDPR compliance
   - Triggers immediate admin alerts

2. worker_pause_events - Operational monitoring of worker pauses
   - Tracks when WORKER_PAUSED env var causes classification skips
   - Enables alerting if worker paused >5 minutes
   - Records which emails were skipped during pause

This implements PRD-0006: Security Monitoring & Alerting.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    """Create security_violations and worker_pause_events tables."""

    # Create security_violations table
    op.create_table(
        'security_violations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('violation_type', sa.String(), nullable=False),
        sa.Column('severity', sa.String(), nullable=False),
        sa.Column('event_metadata', postgresql.JSONB(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
    )

    # Create indexes for security_violations
    op.create_index(
        'ix_security_violations_violation_type',
        'security_violations',
        ['violation_type'],
        unique=False
    )

    op.create_index(
        'ix_security_violations_severity',
        'security_violations',
        ['severity'],
        unique=False
    )

    op.create_index(
        'ix_security_violations_detected_at',
        'security_violations',
        ['detected_at'],
        unique=False
    )

    # Create worker_pause_events table
    op.create_table(
        'worker_pause_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('mailbox_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('paused_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('resumed_at', sa.DateTime(), nullable=True),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['mailbox_id'], ['mailboxes.id'], ),
    )

    # Create indexes for worker_pause_events
    op.create_index(
        'ix_worker_pause_events_mailbox_id',
        'worker_pause_events',
        ['mailbox_id'],
        unique=False
    )

    op.create_index(
        'ix_worker_pause_events_paused_at',
        'worker_pause_events',
        ['paused_at'],
        unique=False
    )


def downgrade():
    """Drop security monitoring tables."""

    # Drop worker_pause_events indexes and table
    op.drop_index('ix_worker_pause_events_paused_at', table_name='worker_pause_events')
    op.drop_index('ix_worker_pause_events_mailbox_id', table_name='worker_pause_events')
    op.drop_table('worker_pause_events')

    # Drop security_violations indexes and table
    op.drop_index('ix_security_violations_detected_at', table_name='security_violations')
    op.drop_index('ix_security_violations_severity', table_name='security_violations')
    op.drop_index('ix_security_violations_violation_type', table_name='security_violations')
    op.drop_table('security_violations')
