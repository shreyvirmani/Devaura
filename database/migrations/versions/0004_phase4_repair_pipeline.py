"""0004_phase4_repair_pipeline: Add repair_id, eligibility, classification to incidents and payload to jobs.

Revision ID: 0004_phase4_repair_pipeline
Revises: 0003_incidents_and_jobs
Create Date: 2026-11-25 18:35:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0004_phase4_repair_pipeline'
down_revision: Union[str, Sequence[str], None] = '0003_incidents_and_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'incidents' in existing_tables:
        inc_cols = {col['name'] for col in inspector.get_columns('incidents')}
        with op.batch_alter_table('incidents', schema=None) as batch_op:
            if 'repair_id' not in inc_cols:
                batch_op.add_column(sa.Column('repair_id', sa.String(length=36), nullable=True))
                batch_op.create_index('ix_incidents_repair_id', ['repair_id'], unique=False)
            if 'eligibility_status' not in inc_cols:
                batch_op.add_column(sa.Column('eligibility_status', sa.Boolean(), nullable=True))
            if 'eligibility_reason' not in inc_cols:
                batch_op.add_column(sa.Column('eligibility_reason', sa.Text(), nullable=True))
            if 'failure_classification' not in inc_cols:
                batch_op.add_column(sa.Column('failure_classification', sa.String(length=60), nullable=True))

    if 'jobs' in existing_tables:
        job_cols = {col['name'] for col in inspector.get_columns('jobs')}
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            if 'payload' not in job_cols:
                batch_op.add_column(sa.Column('payload', sa.JSON(), nullable=False, server_default='{}'))


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'jobs' in existing_tables:
        job_cols = {col['name'] for col in inspector.get_columns('jobs')}
        with op.batch_alter_table('jobs', schema=None) as batch_op:
            if 'payload' in job_cols:
                batch_op.drop_column('payload')

    if 'incidents' in existing_tables:
        inc_cols = {col['name'] for col in inspector.get_columns('incidents')}
        with op.batch_alter_table('incidents', schema=None) as batch_op:
            for col in ['failure_classification', 'eligibility_reason', 'eligibility_status', 'repair_id']:
                if col in inc_cols:
                    batch_op.drop_column(col)
