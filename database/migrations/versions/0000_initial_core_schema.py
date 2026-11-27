"""0000_initial_core_schema: Baseline core tables prior to SaaS multi-tenancy.

Revision ID: 0000_initial_core_schema
Revises: 
Create Date: 2026-11-25 13:20:00
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0000_initial_core_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'users' not in existing_tables:
        op.create_table(
            'users',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    if 'mcp_servers' not in existing_tables:
        op.create_table(
            'mcp_servers',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('transport', sa.String(length=50), nullable=False),
            sa.Column('endpoint', sa.String(length=500), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('configuration', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'evaluation_runs' not in existing_tables:
        op.create_table(
            'evaluation_runs',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('dataset_version', sa.String(length=50), nullable=False),
            sa.Column('total_cases', sa.Integer(), nullable=False),
            sa.Column('passed_cases', sa.Integer(), nullable=False),
            sa.Column('failed_cases', sa.Integer(), nullable=False),
            sa.Column('localization_accuracy_top1', sa.Float(), nullable=False),
            sa.Column('localization_accuracy_top3', sa.Float(), nullable=False),
            sa.Column('root_cause_accuracy', sa.Float(), nullable=False),
            sa.Column('evidence_precision', sa.Float(), nullable=False),
            sa.Column('patch_success_rate', sa.Float(), nullable=False),
            sa.Column('verification_pass_rate', sa.Float(), nullable=False),
            sa.Column('regression_rate', sa.Float(), nullable=False),
            sa.Column('false_repair_rate', sa.Float(), nullable=False),
            sa.Column('average_attempts', sa.Float(), nullable=False),
            sa.Column('safety_violations', sa.Integer(), nullable=False),
            sa.Column('duration_ms', sa.Float(), nullable=False),
            sa.Column('summary_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'mcp_tools' not in existing_tables:
        op.create_table(
            'mcp_tools',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('server_id', sa.String(length=36), sa.ForeignKey('mcp_servers.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('input_schema', sa.JSON(), nullable=False),
            sa.Column('risk_level', sa.String(length=20), nullable=False),
            sa.Column('enabled', sa.Boolean(), nullable=False),
        )
        op.create_index('ix_mcp_tools_name', 'mcp_tools', ['name'], unique=False)

    if 'evaluation_bug_results' not in existing_tables:
        op.create_table(
            'evaluation_bug_results',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('run_id', sa.String(length=36), sa.ForeignKey('evaluation_runs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('bug_id', sa.String(length=50), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('language', sa.String(length=30), nullable=False),
            sa.Column('difficulty', sa.String(length=20), nullable=False),
            sa.Column('localization_passed', sa.Boolean(), nullable=False),
            sa.Column('root_cause_passed', sa.Boolean(), nullable=False),
            sa.Column('patch_generated', sa.Boolean(), nullable=False),
            sa.Column('verification_passed', sa.Boolean(), nullable=False),
            sa.Column('regression_detected', sa.Boolean(), nullable=False),
            sa.Column('attempts_used', sa.Integer(), nullable=False),
            sa.Column('duration_ms', sa.Float(), nullable=False),
            sa.Column('failure_classification', sa.String(length=50), nullable=True),
            sa.Column('trace_id', sa.String(length=64), nullable=True),
            sa.Column('result_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_evaluation_bug_results_bug_id', 'evaluation_bug_results', ['bug_id'], unique=False)
        op.create_index('ix_evaluation_bug_results_run_id', 'evaluation_bug_results', ['run_id'], unique=False)

    if 'repositories' not in existing_tables:
        op.create_table(
            'repositories',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('owner', sa.String(length=100), nullable=False),
            sa.Column('name', sa.String(length=100), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('default_branch', sa.String(length=100), nullable=False),
            sa.Column('clone_url', sa.String(length=500), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_repositories_name', 'repositories', ['name'], unique=False)
        op.create_index('ix_repositories_owner', 'repositories', ['owner'], unique=False)

    if 'investigations' not in existing_tables:
        op.create_table(
            'investigations',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_type', sa.String(length=50), nullable=False),
            sa.Column('source_id', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=True),
            sa.Column('summary', sa.Text(), nullable=False),
            sa.Column('failure_type', sa.String(length=50), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('stack_trace', sa.Text(), nullable=True),
            sa.Column('failed_tests', sa.JSON(), nullable=False),
            sa.Column('ci_run_id', sa.String(length=100), nullable=True),
            sa.Column('commit_sha', sa.String(length=64), nullable=True),
            sa.Column('branch', sa.String(length=100), nullable=True),
            sa.Column('evidence_sufficiency', sa.String(length=50), nullable=False),
            sa.Column('root_cause', sa.Text(), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'code_files' not in existing_tables:
        op.create_table(
            'code_files',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('path', sa.String(length=500), nullable=False),
            sa.Column('language', sa.String(length=50), nullable=False),
            sa.Column('hash', sa.String(length=64), nullable=False),
            sa.Column('size_bytes', sa.Integer(), nullable=False),
            sa.Column('line_count', sa.Integer(), nullable=False),
            sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_code_files_language', 'code_files', ['language'], unique=False)
        op.create_index('ix_code_files_path', 'code_files', ['path'], unique=False)
        op.create_index('ix_code_files_repository_id', 'code_files', ['repository_id'], unique=False)

    if 'code_relationships' not in existing_tables:
        op.create_table(
            'code_relationships',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_type', sa.String(length=50), nullable=False),
            sa.Column('source_id', sa.String(length=36), nullable=False),
            sa.Column('target_type', sa.String(length=50), nullable=False),
            sa.Column('target_id', sa.String(length=255), nullable=False),
            sa.Column('relationship_type', sa.String(length=50), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('resolution_status', sa.String(length=50), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_code_relationships_relationship_type', 'code_relationships', ['relationship_type'], unique=False)
        op.create_index('ix_code_relationships_repository_id', 'code_relationships', ['repository_id'], unique=False)
        op.create_index('ix_code_relationships_source_id', 'code_relationships', ['source_id'], unique=False)
        op.create_index('ix_code_relationships_target_id', 'code_relationships', ['target_id'], unique=False)

    if 'code_index_runs' not in existing_tables:
        op.create_table(
            'code_index_runs',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('files_indexed', sa.Integer(), nullable=False),
            sa.Column('symbols_indexed', sa.Integer(), nullable=False),
            sa.Column('duration_ms', sa.Float(), nullable=False),
            sa.Column('error_message', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_code_index_runs_repository_id', 'code_index_runs', ['repository_id'], unique=False)

    if 'evidence' not in existing_tables:
        op.create_table(
            'evidence',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source', sa.String(length=50), nullable=False),
            sa.Column('type', sa.String(length=50), nullable=False),
            sa.Column('content', sa.Text(), nullable=False),
            sa.Column('repository_path', sa.String(length=500), nullable=True),
            sa.Column('symbol_id', sa.String(length=255), nullable=True),
            sa.Column('line_start', sa.Integer(), nullable=True),
            sa.Column('line_end', sa.Integer(), nullable=True),
            sa.Column('commit_sha', sa.String(length=64), nullable=True),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('relevance', sa.Float(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'root_cause_candidates' not in existing_tables:
        op.create_table(
            'root_cause_candidates',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('title', sa.String(length=255), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('affected_symbols', sa.JSON(), nullable=False),
            sa.Column('affected_files', sa.JSON(), nullable=False),
            sa.Column('supporting_evidence_ids', sa.JSON(), nullable=False),
            sa.Column('contradicting_evidence_ids', sa.JSON(), nullable=False),
            sa.Column('reasoning', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'investigation_steps' not in existing_tables:
        op.create_table(
            'investigation_steps',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('step_number', sa.Integer(), nullable=False),
            sa.Column('action', sa.String(length=100), nullable=False),
            sa.Column('tool_name', sa.String(length=100), nullable=True),
            sa.Column('tool_input', sa.JSON(), nullable=False),
            sa.Column('tool_output', sa.JSON(), nullable=False),
            sa.Column('observation', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_plans' not in existing_tables:
        op.create_table(
            'repair_plans',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('plan', sa.JSON(), nullable=False),
            sa.Column('risk_level', sa.String(length=20), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_attempts' not in existing_tables:
        op.create_table(
            'repair_attempts',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('patch', sa.Text(), nullable=False),
            sa.Column('test_results', sa.JSON(), nullable=False),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        )

    if 'tool_executions' not in existing_tables:
        op.create_table(
            'tool_executions',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='SET NULL'), nullable=True),
            sa.Column('server', sa.String(length=100), nullable=False),
            sa.Column('tool', sa.String(length=100), nullable=False),
            sa.Column('input', sa.JSON(), nullable=False),
            sa.Column('output', sa.JSON(), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('latency_ms', sa.Float(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'pull_requests' not in existing_tables:
        op.create_table(
            'pull_requests',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider_pr_id', sa.String(length=100), nullable=False),
            sa.Column('url', sa.String(length=500), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'code_symbols' not in existing_tables:
        op.create_table(
            'code_symbols',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('file_id', sa.String(length=36), sa.ForeignKey('code_files.id', ondelete='CASCADE'), nullable=False),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('name', sa.String(length=255), nullable=False),
            sa.Column('qualified_name', sa.String(length=500), nullable=False),
            sa.Column('kind', sa.String(length=50), nullable=False),
            sa.Column('start_line', sa.Integer(), nullable=False),
            sa.Column('end_line', sa.Integer(), nullable=False),
            sa.Column('signature', sa.Text(), nullable=True),
            sa.Column('docstring', sa.Text(), nullable=True),
            sa.Column('parent_symbol_id', sa.String(length=36), sa.ForeignKey('code_symbols.id', ondelete='CASCADE'), nullable=True),
            sa.Column('metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_code_symbols_file_id', 'code_symbols', ['file_id'], unique=False)
        op.create_index('ix_code_symbols_kind', 'code_symbols', ['kind'], unique=False)
        op.create_index('ix_code_symbols_name', 'code_symbols', ['name'], unique=False)
        op.create_index('ix_code_symbols_parent_symbol_id', 'code_symbols', ['parent_symbol_id'], unique=False)
        op.create_index('ix_code_symbols_qualified_name', 'code_symbols', ['qualified_name'], unique=False)
        op.create_index('ix_code_symbols_repository_id', 'code_symbols', ['repository_id'], unique=False)

    if 'code_imports' not in existing_tables:
        op.create_table(
            'code_imports',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('file_id', sa.String(length=36), sa.ForeignKey('code_files.id', ondelete='CASCADE'), nullable=False),
            sa.Column('module', sa.String(length=255), nullable=False),
            sa.Column('symbol_name', sa.String(length=255), nullable=True),
            sa.Column('alias', sa.String(length=255), nullable=True),
            sa.Column('is_external', sa.Boolean(), nullable=False),
            sa.Column('line_number', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_code_imports_file_id', 'code_imports', ['file_id'], unique=False)
        op.create_index('ix_code_imports_module', 'code_imports', ['module'], unique=False)

    if 'repairs' not in existing_tables:
        op.create_table(
            'repairs',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('status', sa.String(length=60), nullable=False),
            sa.Column('target_branch', sa.String(length=100), nullable=False),
            sa.Column('base_revision', sa.String(length=64), nullable=False),
            sa.Column('current_attempt', sa.Integer(), nullable=False),
            sa.Column('max_attempts', sa.Integer(), nullable=False),
            sa.Column('latest_verification_id', sa.String(length=36), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_repairs_investigation_id', 'repairs', ['investigation_id'], unique=False)
        op.create_index('ix_repairs_status', 'repairs', ['status'], unique=False)

    if 'verification_runs' not in existing_tables:
        op.create_table(
            'verification_runs',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_attempt_id', sa.String(length=36), sa.ForeignKey('repair_attempts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('test_status', sa.String(length=20), nullable=False),
            sa.Column('lint_status', sa.String(length=20), nullable=False),
            sa.Column('typecheck_status', sa.String(length=20), nullable=False),
            sa.Column('security_status', sa.String(length=20), nullable=False),
            sa.Column('test_output', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'code_test_mappings' not in existing_tables:
        op.create_table(
            'code_test_mappings',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_file_id', sa.String(length=36), sa.ForeignKey('code_files.id', ondelete='CASCADE'), nullable=False),
            sa.Column('test_file_id', sa.String(length=36), sa.ForeignKey('code_files.id', ondelete='CASCADE'), nullable=False),
            sa.Column('source_symbol_id', sa.String(length=36), sa.ForeignKey('code_symbols.id', ondelete='SET NULL'), nullable=True),
            sa.Column('test_symbol_id', sa.String(length=36), sa.ForeignKey('code_symbols.id', ondelete='SET NULL'), nullable=True),
            sa.Column('relationship_type', sa.String(length=50), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_code_test_mappings_repository_id', 'code_test_mappings', ['repository_id'], unique=False)
        op.create_index('ix_code_test_mappings_source_file_id', 'code_test_mappings', ['source_file_id'], unique=False)
        op.create_index('ix_code_test_mappings_source_symbol_id', 'code_test_mappings', ['source_symbol_id'], unique=False)
        op.create_index('ix_code_test_mappings_test_file_id', 'code_test_mappings', ['test_file_id'], unique=False)
        op.create_index('ix_code_test_mappings_test_symbol_id', 'code_test_mappings', ['test_symbol_id'], unique=False)

    if 'repair_contexts' not in existing_tables:
        op.create_table(
            'repair_contexts',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('investigation_id', sa.String(length=36), nullable=False),
            sa.Column('candidate_id', sa.String(length=100), nullable=False),
            sa.Column('affected_files', sa.JSON(), nullable=False),
            sa.Column('affected_symbols', sa.JSON(), nullable=False),
            sa.Column('supporting_evidence_ids', sa.JSON(), nullable=False),
            sa.Column('related_tests', sa.JSON(), nullable=False),
            sa.Column('context_data', sa.JSON(), nullable=False),
            sa.Column('is_valid', sa.Boolean(), nullable=False),
            sa.Column('validation_error', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_plans_v2' not in existing_tables:
        op.create_table(
            'repair_plans_v2',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('objective', sa.Text(), nullable=False),
            sa.Column('root_cause', sa.Text(), nullable=False),
            sa.Column('proposed_changes', sa.JSON(), nullable=False),
            sa.Column('tests_to_run', sa.JSON(), nullable=False),
            sa.Column('risks', sa.JSON(), nullable=False),
            sa.Column('assumptions', sa.JSON(), nullable=False),
            sa.Column('confidence', sa.Float(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_patches' not in existing_tables:
        op.create_table(
            'repair_patches',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('unified_diff', sa.Text(), nullable=False),
            sa.Column('patch_hash', sa.String(length=64), nullable=False),
            sa.Column('changed_files', sa.JSON(), nullable=False),
            sa.Column('lines_added', sa.Integer(), nullable=False),
            sa.Column('lines_removed', sa.Integer(), nullable=False),
            sa.Column('explanation', sa.Text(), nullable=False),
            sa.Column('model_metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_repair_patches_patch_hash', 'repair_patches', ['patch_hash'], unique=False)

    if 'patch_risks' not in existing_tables:
        op.create_table(
            'patch_risks',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('score', sa.Float(), nullable=False),
            sa.Column('level', sa.String(length=20), nullable=False),
            sa.Column('findings', sa.JSON(), nullable=False),
            sa.Column('blocking_findings', sa.JSON(), nullable=False),
            sa.Column('rationale', sa.Text(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_approvals' not in existing_tables:
        op.create_table(
            'repair_approvals',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('patch_hash', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('approved_by', sa.String(length=255), nullable=True),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('approval_token', sa.String(length=64), nullable=False),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_workspaces' not in existing_tables:
        op.create_table(
            'repair_workspaces',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('isolated_path', sa.String(length=500), nullable=False),
            sa.Column('base_revision', sa.String(length=64), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'repair_events' not in existing_tables:
        op.create_table(
            'repair_events',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('event_type', sa.String(length=60), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('metadata', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_repair_events_repair_id', 'repair_events', ['repair_id'], unique=False)

    if 'repair_attempts_v2' not in existing_tables:
        op.create_table(
            'repair_attempts_v2',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False),
            sa.Column('patch_hash', sa.String(length=64), nullable=False),
            sa.Column('unified_diff', sa.Text(), nullable=False),
            sa.Column('approval_token', sa.String(length=64), nullable=True),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_repair_attempts_v2_repair_id', 'repair_attempts_v2', ['repair_id'], unique=False)

    if 'verification_runs_v2' not in existing_tables:
        op.create_table(
            'verification_runs_v2',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False),
            sa.Column('workspace_id', sa.String(length=100), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('overall_result', sa.String(length=30), nullable=False),
            sa.Column('failure_analysis_json', sa.JSON(), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index('ix_verification_runs_v2_repair_id', 'verification_runs_v2', ['repair_id'], unique=False)

    if 'failure_signatures' not in existing_tables:
        op.create_table(
            'failure_signatures',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('attempt_number', sa.Integer(), nullable=False),
            sa.Column('signature_hash', sa.String(length=64), nullable=False),
            sa.Column('check_type', sa.String(length=20), nullable=False),
            sa.Column('error_summary', sa.Text(), nullable=False),
            sa.Column('file_path', sa.String(length=500), nullable=False),
            sa.Column('line_number', sa.Integer(), nullable=True),
            sa.Column('test_name', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_failure_signatures_repair_id', 'failure_signatures', ['repair_id'], unique=False)
        op.create_index('ix_failure_signatures_signature_hash', 'failure_signatures', ['signature_hash'], unique=False)

    if 'pull_requests_v2' not in existing_tables:
        op.create_table(
            'pull_requests_v2',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('investigation_id', sa.String(length=36), sa.ForeignKey('investigations.id', ondelete='CASCADE'), nullable=False),
            sa.Column('repository_id', sa.String(length=36), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
            sa.Column('provider', sa.String(length=50), nullable=False),
            sa.Column('owner', sa.String(length=100), nullable=False),
            sa.Column('repo', sa.String(length=100), nullable=False),
            sa.Column('base_branch', sa.String(length=100), nullable=False),
            sa.Column('base_revision', sa.String(length=64), nullable=False),
            sa.Column('repair_branch', sa.String(length=100), nullable=False),
            sa.Column('commit_sha', sa.String(length=64), nullable=True),
            sa.Column('pr_number', sa.Integer(), nullable=False),
            sa.Column('pr_url', sa.String(length=500), nullable=False),
            sa.Column('pr_title', sa.String(length=255), nullable=False),
            sa.Column('pr_body', sa.Text(), nullable=False),
            sa.Column('pr_state', sa.String(length=50), nullable=False),
            sa.Column('patch_hash', sa.String(length=64), nullable=False),
            sa.Column('verification_id', sa.String(length=36), nullable=True),
            sa.Column('approval_token', sa.String(length=100), nullable=True),
            sa.Column('approved_by', sa.String(length=255), nullable=True),
            sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('status', sa.String(length=60), nullable=False),
            sa.Column('ci_status_json', sa.JSON(), nullable=False),
            sa.Column('review_status_json', sa.JSON(), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_pull_requests_v2_investigation_id', 'pull_requests_v2', ['investigation_id'], unique=False)
        op.create_index('ix_pull_requests_v2_repair_id', 'pull_requests_v2', ['repair_id'], unique=False)
        op.create_index('ix_pull_requests_v2_repository_id', 'pull_requests_v2', ['repository_id'], unique=False)
        op.create_index('ix_pull_requests_v2_status', 'pull_requests_v2', ['status'], unique=False)

    if 'verification_checks' not in existing_tables:
        op.create_table(
            'verification_checks',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('verification_run_id', sa.String(length=36), sa.ForeignKey('verification_runs_v2.id', ondelete='CASCADE'), nullable=False),
            sa.Column('check_type', sa.String(length=20), nullable=False),
            sa.Column('command', sa.String(length=500), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('exit_code', sa.Integer(), nullable=False),
            sa.Column('duration_ms', sa.Float(), nullable=False),
            sa.Column('stdout', sa.Text(), nullable=False),
            sa.Column('stderr', sa.Text(), nullable=False),
            sa.Column('parsed_errors_json', sa.JSON(), nullable=False),
            sa.Column('resource_usage_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index('ix_verification_checks_verification_run_id', 'verification_checks', ['verification_run_id'], unique=False)

    if 'pr_approvals_v2' not in existing_tables:
        op.create_table(
            'pr_approvals_v2',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('pr_record_id', sa.String(length=36), sa.ForeignKey('pull_requests_v2.id', ondelete='CASCADE'), nullable=True),
            sa.Column('patch_hash', sa.String(length=64), nullable=False),
            sa.Column('approval_token', sa.String(length=100), nullable=False),
            sa.Column('approved_by', sa.String(length=255), nullable=False),
            sa.Column('status', sa.String(length=50), nullable=False),
            sa.Column('rejection_reason', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

    if 'pr_events_v2' not in existing_tables:
        op.create_table(
            'pr_events_v2',
            sa.Column('id', sa.String(length=36), primary_key=True),
            sa.Column('repair_id', sa.String(length=36), sa.ForeignKey('repairs.id', ondelete='CASCADE'), nullable=False),
            sa.Column('pr_record_id', sa.String(length=36), sa.ForeignKey('pull_requests_v2.id', ondelete='CASCADE'), nullable=True),
            sa.Column('event_type', sa.String(length=60), nullable=False),
            sa.Column('description', sa.Text(), nullable=False),
            sa.Column('actor', sa.String(length=255), nullable=False),
            sa.Column('metadata_json', sa.JSON(), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        )

def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = set(inspector.get_table_names())

    if 'pr_events_v2' in existing_tables:
        op.drop_table('pr_events_v2')
    if 'pr_approvals_v2' in existing_tables:
        op.drop_table('pr_approvals_v2')
    if 'verification_checks' in existing_tables:
        op.drop_table('verification_checks')
    if 'pull_requests_v2' in existing_tables:
        op.drop_table('pull_requests_v2')
    if 'failure_signatures' in existing_tables:
        op.drop_table('failure_signatures')
    if 'verification_runs_v2' in existing_tables:
        op.drop_table('verification_runs_v2')
    if 'repair_attempts_v2' in existing_tables:
        op.drop_table('repair_attempts_v2')
    if 'repair_events' in existing_tables:
        op.drop_table('repair_events')
    if 'repair_workspaces' in existing_tables:
        op.drop_table('repair_workspaces')
    if 'repair_approvals' in existing_tables:
        op.drop_table('repair_approvals')
    if 'patch_risks' in existing_tables:
        op.drop_table('patch_risks')
    if 'repair_patches' in existing_tables:
        op.drop_table('repair_patches')
    if 'repair_plans_v2' in existing_tables:
        op.drop_table('repair_plans_v2')
    if 'repair_contexts' in existing_tables:
        op.drop_table('repair_contexts')
    if 'code_test_mappings' in existing_tables:
        op.drop_table('code_test_mappings')
    if 'verification_runs' in existing_tables:
        op.drop_table('verification_runs')
    if 'repairs' in existing_tables:
        op.drop_table('repairs')
    if 'code_imports' in existing_tables:
        op.drop_table('code_imports')
    if 'code_symbols' in existing_tables:
        op.drop_table('code_symbols')
    if 'pull_requests' in existing_tables:
        op.drop_table('pull_requests')
    if 'tool_executions' in existing_tables:
        op.drop_table('tool_executions')
    if 'repair_attempts' in existing_tables:
        op.drop_table('repair_attempts')
    if 'repair_plans' in existing_tables:
        op.drop_table('repair_plans')
    if 'investigation_steps' in existing_tables:
        op.drop_table('investigation_steps')
    if 'root_cause_candidates' in existing_tables:
        op.drop_table('root_cause_candidates')
    if 'evidence' in existing_tables:
        op.drop_table('evidence')
    if 'code_index_runs' in existing_tables:
        op.drop_table('code_index_runs')
    if 'code_relationships' in existing_tables:
        op.drop_table('code_relationships')
    if 'code_files' in existing_tables:
        op.drop_table('code_files')
    if 'investigations' in existing_tables:
        op.drop_table('investigations')
    if 'repositories' in existing_tables:
        op.drop_table('repositories')
    if 'evaluation_bug_results' in existing_tables:
        op.drop_table('evaluation_bug_results')
    if 'mcp_tools' in existing_tables:
        op.drop_table('mcp_tools')
    if 'evaluation_runs' in existing_tables:
        op.drop_table('evaluation_runs')
    if 'mcp_servers' in existing_tables:
        op.drop_table('mcp_servers')
    if 'users' in existing_tables:
        op.drop_table('users')
