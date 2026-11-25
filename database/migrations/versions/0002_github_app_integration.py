"""0002_github_app_integration: GitHub App installations, webhooks, and repository metadata.

Revision ID: 0002_github_app_integration
Revises: 0001_saas_foundation
Create Date: 2026-11-25 15:10:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_github_app_integration'
down_revision: Union[str, Sequence[str], None] = '0001_saas_foundation'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Create github_app_installations table if not present
    if 'github_app_installations' not in existing_tables:
        op.create_table(
            'github_app_installations',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('installation_id', sa.Integer(), nullable=False),
            sa.Column('account_id', sa.Integer(), nullable=True),
            sa.Column('account_name', sa.String(length=100), nullable=False),
            sa.Column('account_type', sa.String(length=20), nullable=False, server_default='User'),
            sa.Column('account_avatar_url', sa.String(length=500), nullable=True),
            sa.Column('repository_selection', sa.String(length=20), nullable=False, server_default='all'),
            sa.Column('permissions', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('events', sa.JSON(), nullable=False, server_default='[]'),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('installed_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_github_app_installations_workspace_id', 'github_app_installations', ['workspace_id'], unique=False)
        op.create_index('ix_github_app_installations_installation_id', 'github_app_installations', ['installation_id'], unique=True)

    # 2. Create webhook_events table if not present
    if 'webhook_events' not in existing_tables:
        op.create_table(
            'webhook_events',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('delivery_id', sa.String(length=100), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('installation_id', sa.Integer(), nullable=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='SET NULL'), nullable=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='RECEIVED'),
            sa.Column('signature_verified', sa.Boolean(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_webhook_events_delivery_id', 'webhook_events', ['delivery_id'], unique=True)
        op.create_index('ix_webhook_events_event_type', 'webhook_events', ['event_type'], unique=False)
        op.create_index('ix_webhook_events_installation_id', 'webhook_events', ['installation_id'], unique=False)
        op.create_index('ix_webhook_events_workspace_id', 'webhook_events', ['workspace_id'], unique=False)
        op.create_index('ix_webhook_events_status', 'webhook_events', ['status'], unique=False)

    # 3. Add GitHub integration columns to repositories table
    if 'repositories' in existing_tables:
        repo_cols = {col['name'] for col in inspector.get_columns('repositories')}
        with op.batch_alter_table('repositories', schema=None) as batch_op:
            if 'github_installation_id' not in repo_cols:
                batch_op.add_column(sa.Column('github_installation_id', sa.String(length=36), nullable=True))
                batch_op.create_index('ix_repositories_github_installation_id', ['github_installation_id'], unique=False)
            if 'github_repository_id' not in repo_cols:
                batch_op.add_column(sa.Column('github_repository_id', sa.Integer(), nullable=True))
                batch_op.create_index('ix_repositories_github_repository_id', ['github_repository_id'], unique=False)
            if 'full_name' not in repo_cols:
                batch_op.add_column(sa.Column('full_name', sa.String(length=200), nullable=True))
                batch_op.create_index('ix_repositories_full_name', ['full_name'], unique=False)
            if 'private' not in repo_cols:
                batch_op.add_column(sa.Column('private', sa.Boolean(), nullable=False, server_default='0'))
            if 'connection_status' not in repo_cols:
                batch_op.add_column(sa.Column('connection_status', sa.String(length=30), nullable=False, server_default='CONNECTED'))
            if 'permissions_snapshot' not in repo_cols:
                batch_op.add_column(sa.Column('permissions_snapshot', sa.JSON(), nullable=False, server_default='{}'))
            if 'last_webhook_received_at' not in repo_cols:
                batch_op.add_column(sa.Column('last_webhook_received_at', sa.DateTime(timezone=True), nullable=True))
            if 'last_indexed_at' not in repo_cols:
                batch_op.add_column(sa.Column('last_indexed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'repositories' in existing_tables:
        repo_cols = {col['name'] for col in inspector.get_columns('repositories')}
        with op.batch_alter_table('repositories', schema=None) as batch_op:
            for col in [
                'last_indexed_at',
                'last_webhook_received_at',
                'permissions_snapshot',
                'connection_status',
                'private',
                'full_name',
                'github_repository_id',
                'github_installation_id',
            ]:
                if col in repo_cols:
                    batch_op.drop_column(col)

    if 'webhook_events' in existing_tables:
        op.drop_table('webhook_events')

    if 'github_app_installations' in existing_tables:
        op.drop_table('github_app_installations')
