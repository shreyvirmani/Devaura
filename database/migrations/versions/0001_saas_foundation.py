"""0001_saas_foundation: Multi-tenancy, workspace memberships, and audit events.

Revision ID: 0001_saas_foundation
Revises: 0000_initial_core_schema
Create Date: 2026-11-25 13:25:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_saas_foundation'
down_revision: Union[str, Sequence[str], None] = '0000_initial_core_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    # 1. Create workspaces table if not present
    if 'workspaces' not in existing_tables:
        op.create_table(
            'workspaces',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('slug', sa.String(length=100), nullable=False),
            sa.Column('owner_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
            sa.Column('settings', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_workspaces_slug', 'workspaces', ['slug'], unique=True)
        op.create_index('ix_workspaces_owner_id', 'workspaces', ['owner_id'], unique=False)

    # 2. Create workspace_members table if not present
    if 'workspace_members' not in existing_tables:
        op.create_table(
            'workspace_members',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=False),
            sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
            sa.Column('role', sa.String(length=20), nullable=False, server_default='MEMBER'),
            sa.Column('invited_by', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_member'),
        )
        op.create_index('ix_workspace_members_workspace_id', 'workspace_members', ['workspace_id'], unique=False)
        op.create_index('ix_workspace_members_user_id', 'workspace_members', ['user_id'], unique=False)

    # 3. Create audit_events table if not present
    if 'audit_events' not in existing_tables:
        op.create_table(
            'audit_events',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('workspace_id', sa.String(length=36), sa.ForeignKey('workspaces.id', ondelete='CASCADE'), nullable=True),
            sa.Column('actor_id', sa.String(length=36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
            sa.Column('actor_email', sa.String(length=255), nullable=True),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('resource_type', sa.String(length=50), nullable=False),
            sa.Column('resource_id', sa.String(length=100), nullable=True),
            sa.Column('outcome', sa.String(length=20), nullable=False, server_default='SUCCESS'),
            sa.Column('details', sa.JSON(), nullable=False, server_default='{}'),
            sa.Column('ip_address', sa.String(length=45), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_audit_events_workspace_id', 'audit_events', ['workspace_id'], unique=False)
        op.create_index('ix_audit_events_actor_id', 'audit_events', ['actor_id'], unique=False)
        op.create_index('ix_audit_events_action', 'audit_events', ['action'], unique=False)
        op.create_index('ix_audit_events_created_at', 'audit_events', ['created_at'], unique=False)

    # 4. Safe column updates for existing tables
    if 'users' in existing_tables:
        user_cols = {c['name'] for c in inspector.get_columns('users')}
        with op.batch_alter_table('users') as batch_op:
            if 'hashed_password' not in user_cols:
                batch_op.add_column(sa.Column('hashed_password', sa.String(length=255), nullable=True))
            if 'is_active' not in user_cols:
                batch_op.add_column(sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'))
            if 'is_superuser' not in user_cols:
                batch_op.add_column(sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='0'))

    if 'repositories' in existing_tables:
        repo_cols = {c['name'] for c in inspector.get_columns('repositories')}
        with op.batch_alter_table('repositories') as batch_op:
            if 'workspace_id' not in repo_cols:
                batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
                batch_op.create_index('ix_repositories_workspace_id', ['workspace_id'])
                batch_op.create_foreign_key('fk_repositories_workspace_id', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')

    if 'investigations' in existing_tables:
        inv_cols = {c['name'] for c in inspector.get_columns('investigations')}
        with op.batch_alter_table('investigations') as batch_op:
            if 'workspace_id' not in inv_cols:
                batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
                batch_op.create_index('ix_investigations_workspace_id', ['workspace_id'])
                batch_op.create_foreign_key('fk_investigations_workspace_id', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')

    if 'repairs' in existing_tables:
        rep_cols = {c['name'] for c in inspector.get_columns('repairs')}
        with op.batch_alter_table('repairs') as batch_op:
            if 'workspace_id' not in rep_cols:
                batch_op.add_column(sa.Column('workspace_id', sa.String(length=36), nullable=True))
                batch_op.create_index('ix_repairs_workspace_id', ['workspace_id'])
                batch_op.create_foreign_key('fk_repairs_workspace_id', 'workspaces', ['workspace_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'repairs' in existing_tables:
        rep_indices = {i['name'] for i in inspector.get_indexes('repairs')}
        rep_cols = {c['name'] for c in inspector.get_columns('repairs')}
        with op.batch_alter_table('repairs') as batch_op:
            if 'ix_repairs_workspace_id' in rep_indices:
                batch_op.drop_index('ix_repairs_workspace_id')
            if 'workspace_id' in rep_cols:
                batch_op.drop_column('workspace_id')

    if 'investigations' in existing_tables:
        inv_indices = {i['name'] for i in inspector.get_indexes('investigations')}
        inv_cols = {c['name'] for c in inspector.get_columns('investigations')}
        with op.batch_alter_table('investigations') as batch_op:
            if 'ix_investigations_workspace_id' in inv_indices:
                batch_op.drop_index('ix_investigations_workspace_id')
            if 'workspace_id' in inv_cols:
                batch_op.drop_column('workspace_id')

    if 'repositories' in existing_tables:
        repo_indices = {i['name'] for i in inspector.get_indexes('repositories')}
        repo_cols = {c['name'] for c in inspector.get_columns('repositories')}
        with op.batch_alter_table('repositories') as batch_op:
            if 'ix_repositories_workspace_id' in repo_indices:
                batch_op.drop_index('ix_repositories_workspace_id')
            if 'workspace_id' in repo_cols:
                batch_op.drop_column('workspace_id')

    if 'users' in existing_tables:
        user_cols = {c['name'] for c in inspector.get_columns('users')}
        with op.batch_alter_table('users') as batch_op:
            if 'is_superuser' in user_cols:
                batch_op.drop_column('is_superuser')
            if 'is_active' in user_cols:
                batch_op.drop_column('is_active')
            if 'hashed_password' in user_cols:
                batch_op.drop_column('hashed_password')

    if 'audit_events' in existing_tables:
        op.drop_table('audit_events')

    if 'workspace_members' in existing_tables:
        op.drop_table('workspace_members')

    if 'workspaces' in existing_tables:
        op.drop_table('workspaces')
