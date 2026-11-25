"""0003_incidents_and_jobs: First-class Incident lifecycle and Durable Job Execution models.

Revision ID: 0003_incidents_and_jobs
Revises: 0002_github_app_integration
Create Date: 2026-11-25 16:05:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003_incidents_and_jobs'
down_revision: Union[str, Sequence[str], None] = '0002_github_app_integration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'incidents' not in existing_tables:
        op.create_table(
            'incidents',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('source', sa.String(length=50), nullable=False, server_default='github_workflow_run'),
            sa.Column('external_event_id', sa.String(length=100), nullable=True),
            sa.Column('external_run_id', sa.String(length=100), nullable=True),
            sa.Column('external_check_id', sa.String(length=100), nullable=True),
            sa.Column('dedup_key', sa.String(length=255), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False, server_default='CI_FAILURE'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='NEW'),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('summary', sa.Text(), nullable=False, server_default=''),
            sa.Column('failure_signature', sa.String(length=255), nullable=True),
            sa.Column('commit_sha', sa.String(length=64), nullable=True),
            sa.Column('branch', sa.String(length=150), nullable=True),
            sa.Column('workflow_name', sa.String(length=200), nullable=True),
            sa.Column('workflow_run_url', sa.String(length=500), nullable=True),
            sa.Column('correlation_id', sa.String(length=64), nullable=False),
            sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=False, server_default='{}'),
        )
        op.create_index('ix_incidents_workspace_id', 'incidents', ['workspace_id'], unique=False)
        op.create_index('ix_incidents_repository_id', 'incidents', ['repository_id'], unique=False)
        op.create_index('ix_incidents_investigation_id', 'incidents', ['investigation_id'], unique=False)
        op.create_index('ix_incidents_external_run_id', 'incidents', ['external_run_id'], unique=False)
        op.create_index('ix_incidents_external_check_id', 'incidents', ['external_check_id'], unique=False)
        op.create_index('ix_incidents_dedup_key', 'incidents', ['dedup_key'], unique=True)
        op.create_index('ix_incidents_status', 'incidents', ['status'], unique=False)
        op.create_index('ix_incidents_correlation_id', 'incidents', ['correlation_id'], unique=False)

    if 'jobs' not in existing_tables:
        op.create_table(
            'jobs',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('incident_id', sa.String(length=36), sa.ForeignKey('incidents.id', ondelete='CASCADE'), nullable=False),
            sa.Column('job_type', sa.String(length=50), nullable=False, server_default='INVESTIGATE_INCIDENT'),
            sa.Column('status', sa.String(length=50), nullable=False, server_default='QUEUED'),
            sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
            sa.Column('available_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('worker_id', sa.String(length=100), nullable=True),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('failure_classification', sa.String(length=50), nullable=True),
            sa.Column('correlation_id', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_jobs_workspace_id', 'jobs', ['workspace_id'], unique=False)
        op.create_index('ix_jobs_incident_id', 'jobs', ['incident_id'], unique=False)
        op.create_index('ix_jobs_status', 'jobs', ['status'], unique=False)
        op.create_index('ix_jobs_available_at', 'jobs', ['available_at'], unique=False)
        op.create_index('ix_jobs_lease_expires_at', 'jobs', ['lease_expires_at'], unique=False)
        op.create_index('ix_jobs_correlation_id', 'jobs', ['correlation_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'jobs' in existing_tables:
        op.drop_table('jobs')
    if 'incidents' in existing_tables:
        op.drop_table('incidents')
