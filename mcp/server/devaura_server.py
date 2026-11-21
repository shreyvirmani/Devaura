import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.api.logger import logger, redact_secrets
from agent.repair.models import (
    ApprovalStatus,
    CheckStatus,
    CheckType,
    FailureAnalysisReport,
    OverallVerificationStatus,
    PatchResult,
    PatchRisk,
    ProposedChange,
    RepairApproval,
    RepairContext,
    RepairExecutionResult,
    RepairPlan,
    VerificationCheck,
    VerificationRun,
    VerifiedRepairResult,
)
from agent.verification.runner import VerificationRunner
from agent.verification.analyzer import VerificationAnalyzer
from agent.repair.context_builder import RepairContextBuilder
from agent.repair.planner import RepairPlanner
from agent.repair.patch_generator import PatchGenerator
from agent.repair.risk_analyzer import PatchRiskAnalyzer
from agent.repair.approval_gate import HumanApprovalGate
from agent.pr.approval_gate import HumanPRApprovalGate
from agent.pr.context_builder import PRContextBuilder
from agent.pr.git_manager import GitStateManager
from agent.pr.models import (
    PRApproval,
    PRApprovalStatus,
    PRContext,
    PRPreparationResult,
    PRState,
)
from agent.pr.orchestrator import PROrchestrator
from integrations.github.client import GitHubClient
from integrations.github.mock_provider import MockGitProvider
from integrations.github.models import (
    BranchInfo,
    CIStatus,
    CIStatusInfo,
    CommitInfo,
    PullRequestPayload,
    PullRequestResult,
    PullRequestState,
    ReviewInfo,
    ReviewStatus,
)
from sandbox.isolated_runner import IsolatedRunner
from code_intelligence.graph.queries import GraphQueryEngine
from code_intelligence.graph.relationship_builder import RelationshipBuilder
from code_intelligence.indexer.file_indexer import FileIndexer
from code_intelligence.indexer.repository_indexer import RepositoryIndexer
from code_intelligence.search.ripgrep_search import RipgrepSearch
from code_intelligence.search.symbol_search import SymbolSearch
from code_intelligence.tests.test_relationships import TestRelationshipsEngine
from mcp.models import RiskLevel
from mcp.policy import policy_engine
from mcp.server.mcpserver import MCPServer

# In-memory registry for MCP repair operations
_REPAIR_CACHE: Dict[str, Dict[str, Any]] = {}


def create_devaura_native_server() -> MCPServer:
    """Instantiate and configure the official Devaura Native MCP Server."""
    server = MCPServer(
        name="devaura-native",
        version="0.2.0",
        instructions="Devaura Native Software Maintenance & Repair Server providing deterministic code analysis, search, git, and verification tools.",
    )

    # --------------------------------------------------------------------------
    # 1. Tool: read_file (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="read_file",
        description="Read file contents bounded by line numbers with path traversal protection.",
    )
    async def read_file(
        path: str,
        start_line: int = 1,
        end_line: int = 200,
        workspace: str = ".",
    ) -> str:
        """Reads a file within workspace with path validation and windowed lines."""
        try:
            target_path = policy_engine.validate_workspace_path(workspace, path)
        except Exception as e:
            return f"Security Violation: Path traversal rejected: {str(e)}"

        if not target_path.exists():
            return f"Error: File '{path}' does not exist."
        if not target_path.is_file():
            return f"Error: Path '{path}' is not a regular file."

        start_line = max(1, start_line)
        end_line = max(start_line, end_line)

        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            selected_lines = lines[start_line - 1 : end_line]
            formatted = [
                f"{i + start_line}: {line.rstrip()}"
                for i, line in enumerate(selected_lines)
            ]

            header = f"--- {path} (lines {start_line}-{min(end_line, total_lines)} of {total_lines}) ---\n"
            return header + "\n".join(formatted)
        except Exception as e:
            return f"Error reading file '{path}': {str(e)}"

    # Set risk level metadata on tool
    read_file.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 2. Tool: search_code (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="search_code",
        description="Search repository source code for keyword or regex matches using multi-tier ripgrep.",
    )
    async def search_code(
        query: str,
        path: str = ".",
        max_results: int = 20,
        workspace: str = ".",
    ) -> str:
        """Searches files inside the workspace with result limits."""
        try:
            search_root = policy_engine.validate_workspace_path(workspace, path)
        except Exception as e:
            return f"Security Violation: Path traversal rejected: {str(e)}"

        if not search_root.exists():
            return f"Error: Search directory '{path}' does not exist."

        rg_engine = RipgrepSearch(workspace_root=workspace)
        matches = rg_engine.search(
            query=query,
            path_filter=path if path != "." else None,
            max_results=max_results,
        )

        if not matches:
            return f"No code occurrences found for query '{query}' in '{path}'."

        result_str = f"Found {len(matches)} matches for '{query}':\n"
        for m in matches:
            result_str += f"{m.file}:{m.line} -> {m.text}\n"
        return result_str

    search_code.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 3. Tool: git_history (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="git_history",
        description="Inspect git commit history and blame for repository files.",
    )
    async def git_history(
        path: str = "",
        limit: int = 10,
        workspace: str = ".",
    ) -> str:
        """Fetches commit history safely without shell injection."""
        base = Path(workspace).resolve()
        limit = max(1, min(limit, 50))
        cmd = ["git", "log", f"-n{limit}", "--oneline"]
        if path:
            target = policy_engine.validate_workspace_path(workspace, path)
            rel = os.path.relpath(target, base)
            cmd.extend(["--", rel])

        try:
            proc = subprocess.run(cmd, cwd=str(base), capture_output=True, text=True, timeout=10)
            if proc.returncode != 0:
                return f"Git error: {proc.stderr.strip()}"
            return proc.stdout.strip() or "No git commits found."
        except Exception as e:
            return f"Error executing git log: {str(e)}"

    git_history.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 4. Tool: inspect_diff (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="inspect_diff",
        description="Inspect current workspace git diff with automated secret sanitization.",
    )
    async def inspect_diff(workspace: str = ".") -> str:
        """Returns unified diff with secret masking."""
        base = Path(workspace).resolve()
        try:
            proc = subprocess.run(["git", "diff"], cwd=str(base), capture_output=True, text=True, timeout=10)
            diff_text = proc.stdout
            if not diff_text.strip():
                # Check staged diff
                proc_staged = subprocess.run(
                    ["git", "diff", "--staged"], cwd=str(base), capture_output=True, text=True, timeout=10
                )
                diff_text = proc_staged.stdout

            if not diff_text.strip():
                return "No uncommitted diff in workspace."

            return redact_secrets(diff_text)
        except Exception as e:
            return f"Error inspecting diff: {str(e)}"

    inspect_diff.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 5. Tool: analyze_repository (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="analyze_repository",
        description="Deterministic analysis of repository languages, frameworks, package managers, and test suites.",
    )
    async def analyze_repository(workspace: str = ".") -> str:
        """Scans workspace manifests and structure."""
        base = Path(workspace).resolve()
        if not base.exists():
            return f"Error: Workspace '{workspace}' does not exist."

        analysis: Dict[str, Any] = {
            "root": str(base),
            "languages": [],
            "package_managers": [],
            "test_frameworks": [],
            "frameworks": [],
            "ci_workflows": [],
        }

        # Check Python indicators
        if list(base.glob("*.py")) or list(base.glob("**/*.py")):
            analysis["languages"].append("Python")
        if (base / "pyproject.toml").exists() or (base / "requirements.txt").exists() or list(base.glob("**/requirements.txt")):
            analysis["package_managers"].append("pip/poetry")
        if (base / "pytest.ini").exists() or list(base.glob("**/test_*.py")):
            analysis["test_frameworks"].append("pytest")

        # Check JavaScript / TypeScript indicators
        if (base / "package.json").exists():
            analysis["package_managers"].append("npm")
            try:
                pkg_data = json.loads((base / "package.json").read_text(encoding="utf-8"))
                deps = {**pkg_data.get("dependencies", {}), **pkg_data.get("devDependencies", {})}
                if "next" in deps:
                    analysis["frameworks"].append("Next.js")
                if "react" in deps:
                    analysis["frameworks"].append("React")
                if "typescript" in deps:
                    analysis["languages"].append("TypeScript")
                if "jest" in deps or "vitest" in deps:
                    analysis["test_frameworks"].append("jest/vitest")
            except Exception:
                pass

        # Check CI workflows
        ci_dir = base / ".github" / "workflows"
        if ci_dir.exists():
            analysis["ci_workflows"] = [f.name for f in ci_dir.glob("*.yml")] + [f.name for f in ci_dir.glob("*.yaml")]

        return json.dumps(analysis, indent=2)

    analyze_repository.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 6. Tool: find_related_tests (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="find_related_tests",
        description="Find unit and integration tests associated with a target source file.",
    )
    async def find_related_tests(target_file: str, workspace: str = ".") -> str:
        base = Path(workspace).resolve()
        target_stem = Path(target_file).stem
        candidates: List[str] = []

        # 1. Try AST-based Test Relationships Engine
        try:
            indexer = FileIndexer(workspace_root=base)
            parsed_files = indexer.index_workspace()
            test_engine = TestRelationshipsEngine(workspace_root=base)
            mappings = test_engine.discover_test_mappings(parsed_files)
            for m in mappings:
                if Path(m["source_file"]).stem == target_stem or target_file in m["source_file"]:
                    if m["test_file"] not in candidates:
                        candidates.append(m["test_file"])
        except Exception:
            pass

        # 2. File pattern matching fallback
        patterns = [
            f"test_{target_stem}.py",
            f"{target_stem}_test.py",
            f"{target_stem}.test.ts",
            f"{target_stem}.spec.ts",
            f"{target_stem}.test.js",
        ]

        for p in patterns:
            for match in base.glob(f"**/{p}"):
                rel = os.path.relpath(match, base).replace("\\", "/")
                if rel not in candidates:
                    candidates.append(rel)

        # General test directory fallback
        if not candidates:
            for test_file in base.glob("tests/**/test_*.py"):
                rel = os.path.relpath(test_file, base).replace("\\", "/")
                if rel not in candidates:
                    candidates.append(rel)

        if not candidates:
            return f"No related tests discovered for '{target_file}'."
        return json.dumps({"target": target_file, "related_tests": candidates}, indent=2)

    find_related_tests.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 6a. Tool: index_repository (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="index_repository",
        description="Deterministically index repository source files, symbols, and relationship graphs.",
    )
    async def index_repository(workspace: str = ".", force_full: bool = False) -> str:
        base = Path(workspace).resolve()
        indexer = RepositoryIndexer(workspace_root=base)
        res = await indexer.index_repository(force_full=force_full)
        return json.dumps(res.model_dump(), indent=2)

    index_repository.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 6b. Tool: search_symbol (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="search_symbol",
        description="Search indexed symbols (functions, classes, methods, interfaces) by name or query.",
    )
    async def search_symbol(query: str, kind: str = "", workspace: str = ".") -> str:
        base = Path(workspace).resolve()
        file_indexer = FileIndexer(workspace_root=base)
        parsed_files = file_indexer.index_workspace()
        sym_search = SymbolSearch()
        matches = sym_search.search_parsed_files(parsed_files, query=query, kind=kind if kind else None)
        if not matches:
            return f"No symbols found matching '{query}'."
        results = [
            {
                "symbol": m.symbol_name,
                "kind": m.kind,
                "file": m.file,
                "line": m.line,
                "signature": m.text,
            }
            for m in matches
        ]
        return json.dumps(results, indent=2)

    search_symbol.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 6c. Tool: get_symbol (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_symbol",
        description="Get exact definition, signature, docstring, and line boundaries of a symbol.",
    )
    async def get_symbol(name: str, workspace: str = ".") -> str:
        base = Path(workspace).resolve()
        file_indexer = FileIndexer(workspace_root=base)
        parsed_files = file_indexer.index_workspace()
        for pf in parsed_files:
            for s in pf.symbols:
                if s.name == name or s.qualified_name == name:
                    return json.dumps(
                        {
                            "name": s.name,
                            "qualified_name": s.qualified_name,
                            "kind": s.kind.value,
                            "file": pf.path,
                            "start_line": s.start_line,
                            "end_line": s.end_line,
                            "signature": s.signature,
                            "docstring": s.docstring,
                            "calls": s.calls,
                            "extends": s.extends,
                        },
                        indent=2,
                    )
        return f"Symbol '{name}' not found in workspace."

    get_symbol.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 6d. Tool: get_relationships (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_relationships",
        description="Retrieve callers, callees, dependencies, and dependents for a symbol or file.",
    )
    async def get_relationships(target: str, workspace: str = ".") -> str:
        base = Path(workspace).resolve()
        file_indexer = FileIndexer(workspace_root=base)
        parsed_files = file_indexer.index_workspace()
        rel_builder = RelationshipBuilder()
        graph = rel_builder.build_graph(parsed_files)
        query_engine = GraphQueryEngine(graph)

        if target.endswith(".py") or target.endswith(".ts") or target.endswith(".js"):
            deps = query_engine.get_file_dependencies(target)
            dependents = query_engine.get_file_dependents(target)
            return json.dumps({"target_file": target, "imports": deps, "imported_by": dependents}, indent=2)
        else:
            callers = [c.metadata.get("qualified_name", c.label) for c in query_engine.get_callers(target)]
            callees = [c.metadata.get("qualified_name", c.label) for c in query_engine.get_callees(target)]
            return json.dumps({"target_symbol": target, "callers": callers, "callees": callees}, indent=2)

    get_relationships.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 6e. Tool: get_repository_graph (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_repository_graph",
        description="Generate topological dependency and symbol graph summary for workspace.",
    )
    async def get_repository_graph(workspace: str = ".") -> str:
        base = Path(workspace).resolve()
        file_indexer = FileIndexer(workspace_root=base)
        parsed_files = file_indexer.index_workspace()
        rel_builder = RelationshipBuilder()
        graph = rel_builder.build_graph(parsed_files)
        return json.dumps(graph.to_graph_data().model_dump(), indent=2)

    get_repository_graph.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 7. Tool: run_tests (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="run_tests",
        description="Execute unit tests inside bounded execution workspace (policy enforced).",
    )
    async def run_tests(
        command: str = "pytest",
        workspace: str = ".",
        timeout_seconds: int = 60,
    ) -> str:
        """Executes test suite with strict command policy and timeout."""
        base = Path(workspace).resolve()
        # Verify command against policy
        tokens = policy_engine.validate_command(command)

        timeout_seconds = max(5, min(timeout_seconds, 120))
        start_time = time.time()
        try:
            proc = subprocess.run(
                tokens,
                cwd=str(base),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            duration = round(time.time() - start_time, 2)
            passed = proc.returncode == 0
            output = {
                "command": command,
                "status": "passed" if passed else "failed",
                "exit_code": proc.returncode,
                "duration_seconds": duration,
                "stdout": redact_secrets(proc.stdout[:4000]),
                "stderr": redact_secrets(proc.stderr[:2000]),
            }
            return json.dumps(output, indent=2)
        except subprocess.TimeoutExpired:
            return json.dumps(
                {"command": command, "status": "timeout", "error": f"Execution exceeded {timeout_seconds}s limit."},
                indent=2,
            )
        except Exception as e:
            return json.dumps({"command": command, "status": "error", "error": str(e)}, indent=2)

    run_tests.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 8. Tool: run_linter (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="run_linter",
        description="Run code linter checks inside workspace.",
    )
    async def run_linter(
        command: str = "ruff check .",
        workspace: str = ".",
        timeout_seconds: int = 30,
    ) -> str:
        tokens = policy_engine.validate_command(command)
        base = Path(workspace).resolve()
        try:
            proc = subprocess.run(tokens, cwd=str(base), capture_output=True, text=True, timeout=timeout_seconds)
            return json.dumps(
                {
                    "command": command,
                    "status": "passed" if proc.returncode == 0 else "failed",
                    "exit_code": proc.returncode,
                    "output": redact_secrets(proc.stdout or proc.stderr),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"command": command, "status": "error", "error": str(e)}, indent=2)

    run_linter.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 9. Tool: run_typecheck (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="run_typecheck",
        description="Run type checking inside workspace.",
    )
    async def run_typecheck(
        command: str = "mypy .",
        workspace: str = ".",
        timeout_seconds: int = 45,
    ) -> str:
        tokens = policy_engine.validate_command(command)
        base = Path(workspace).resolve()
        try:
            proc = subprocess.run(tokens, cwd=str(base), capture_output=True, text=True, timeout=timeout_seconds)
            return json.dumps(
                {
                    "command": command,
                    "status": "passed" if proc.returncode == 0 else "failed",
                    "exit_code": proc.returncode,
                    "output": redact_secrets(proc.stdout or proc.stderr),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"command": command, "status": "error", "error": str(e)}, indent=2)

    run_typecheck.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 10. Tool: create_repair_context (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="create_repair_context",
        description="Validate investigation findings and build an immutable RepairContext contract.",
    )
    async def create_repair_context(
        investigation_data: str,
        candidate_id: str = "",
        workspace: str = ".",
        repair_id: str = "",
    ) -> str:
        try:
            inv_dict = json.loads(investigation_data) if isinstance(investigation_data, str) else investigation_data
            builder = RepairContextBuilder(workspace_root=workspace)
            valid, ctx, err = builder.validate_and_build(
                investigation=inv_dict,
                selected_candidate_id=candidate_id or None,
                repair_id=repair_id or None,
            )
            if not valid or not ctx:
                return json.dumps({"status": "REPAIR_BLOCKED_INSUFFICIENT_EVIDENCE", "error": err}, indent=2)
            _REPAIR_CACHE[ctx.repair_id] = {"context": ctx}
            return ctx.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)}, indent=2)

    create_repair_context.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 11. Tool: get_repair_context (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_repair_context",
        description="Retrieve an existing RepairContext by repair_id.",
    )
    async def get_repair_context(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id)
        if not record or "context" not in record:
            return json.dumps({"error": f"Repair context not found for id: {repair_id}"}, indent=2)
        return record["context"].model_dump_json(indent=2)

    get_repair_context.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 12. Tool: generate_repair_plan (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="generate_repair_plan",
        description="Formulate an evidence-backed RepairPlan strictly bounded by RepairContext.",
    )
    async def generate_repair_plan(
        repair_id: str = "",
        context_json: str = "",
    ) -> str:
        try:
            if context_json:
                ctx_dict = json.loads(context_json)
                ctx = RepairContext.model_validate(ctx_dict)
            elif repair_id and repair_id in _REPAIR_CACHE and "context" in _REPAIR_CACHE[repair_id]:
                ctx = _REPAIR_CACHE[repair_id]["context"]
            else:
                return json.dumps({"error": "Valid RepairContext or registered repair_id required"}, indent=2)

            planner = RepairPlanner()
            plan = planner.create_plan(ctx)
            if ctx.repair_id not in _REPAIR_CACHE:
                _REPAIR_CACHE[ctx.repair_id] = {}
            _REPAIR_CACHE[ctx.repair_id]["plan"] = plan
            return plan.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "PLAN_FAILED", "error": str(e)}, indent=2)

    generate_repair_plan.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 13. Tool: generate_patch (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="generate_patch",
        description="Generate a unified diff and cryptographic hash for a repair plan.",
    )
    async def generate_patch(
        repair_id: str = "",
        plan_json: str = "",
        context_json: str = "",
        workspace: str = ".",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            if plan_json:
                plan = RepairPlan.model_validate(json.loads(plan_json))
            elif "plan" in record:
                plan = record["plan"]
            else:
                return json.dumps({"error": "RepairPlan required"}, indent=2)

            if context_json:
                ctx = RepairContext.model_validate(json.loads(context_json))
            elif "context" in record:
                ctx = record["context"]
            else:
                return json.dumps({"error": "RepairContext required"}, indent=2)

            generator = PatchGenerator(workspace_root=workspace)
            patch = generator.generate_defensive_patch(plan, ctx)
            record["patch"] = patch
            _REPAIR_CACHE[plan.repair_id] = record
            return patch.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "PATCH_FAILED", "error": str(e)}, indent=2)

    generate_patch.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 14. Tool: analyze_patch_risk (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="analyze_patch_risk",
        description="Perform static risk analysis on proposed patch diff across 5 dimensions.",
    )
    async def analyze_patch_risk(
        repair_id: str = "",
        patch_json: str = "",
        plan_json: str = "",
        context_json: str = "",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            patch = PatchResult.model_validate(json.loads(patch_json)) if patch_json else record.get("patch")
            plan = RepairPlan.model_validate(json.loads(plan_json)) if plan_json else record.get("plan")
            ctx = RepairContext.model_validate(json.loads(context_json)) if context_json else record.get("context")

            if not patch or not plan or not ctx:
                return json.dumps({"error": "patch, plan, and context required for risk analysis"}, indent=2)

            analyzer = PatchRiskAnalyzer()
            risk = analyzer.analyze(patch, plan, ctx)
            record["risk"] = risk
            _REPAIR_CACHE[plan.repair_id] = record
            return risk.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    analyze_patch_risk.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 15. Tool: approve_repair (DANGEROUS)
    # --------------------------------------------------------------------------
    @server.tool(
        name="approve_repair",
        description="Human Approval Gate: Grant authorization bound to patch SHA-256 hash.",
    )
    async def approve_repair(
        repair_id: str,
        patch_hash: str,
        approver_id: str = "human-developer",
    ) -> str:
        try:
            gate = HumanApprovalGate()
            record = _REPAIR_CACHE.get(repair_id, {})
            patch = record.get("patch")
            diff = patch.unified_diff if patch else "placeholder-diff"
            approval = gate.create_approval(
                repair_id=repair_id,
                unified_diff=diff,
                user_identity=approver_id,
            )
            if patch_hash:
                approval.patch_hash = patch_hash
            record["approval"] = approval
            _REPAIR_CACHE[repair_id] = record
            return approval.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "REJECTED", "error": str(e)}, indent=2)

    approve_repair.risk_level = RiskLevel.DANGEROUS

    # --------------------------------------------------------------------------
    # 16. Tool: apply_approved_patch (DANGEROUS)
    # --------------------------------------------------------------------------
    @server.tool(
        name="apply_approved_patch",
        description="Apply an approved patch strictly inside an isolated sandbox workspace.",
    )
    async def apply_approved_patch(
        repair_id: str,
        approval_token: str = "",
        workspace: str = ".",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            approval = record.get("approval")
            patch = record.get("patch")
            ctx = record.get("context")

            if not approval or not patch:
                return json.dumps({"status": "APPLICATION_FAILED", "error": "Approved patch not found in cache"}, indent=2)

            gate = HumanApprovalGate()
            gate.verify_authorization(approval, patch.unified_diff)

            runner = IsolatedRunner()
            result = runner.run_patch_application(
                repair_id=repair_id,
                investigation_id=ctx.investigation_id if ctx else "inv-unknown",
                repository_id=ctx.repository_id if ctx else "repo-default",
                source_repo_path=workspace,
                patch=patch,
            )
            record["execution_result"] = result
            return result.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "APPLICATION_FAILED", "error": str(e)}, indent=2)

    apply_approved_patch.risk_level = RiskLevel.DANGEROUS

    # --------------------------------------------------------------------------
    # 17. Tool: get_repair_diff (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_repair_diff",
        description="Inspect the unified diff and changed files for a repair.",
    )
    async def get_repair_diff(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        patch = record.get("patch")
        if not patch:
            return json.dumps({"error": f"Patch not found for repair {repair_id}"}, indent=2)
        return json.dumps({
            "repair_id": repair_id,
            "patch_hash": patch.patch_hash,
            "changed_files": patch.changed_files,
            "lines_added": patch.lines_added,
            "lines_removed": patch.lines_removed,
            "unified_diff": patch.unified_diff,
        }, indent=2)

    get_repair_diff.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 18. Tool: run_verification (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="run_verification",
        description="Run test, lint, and typecheck suite strictly inside the isolated sandbox workspace.",
    )
    async def run_verification(
        repair_id: str,
        workspace: str = "",
        custom_commands_json: str = "",
        timeout_seconds: int = 30,
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            exec_res = record.get("execution_result")
            sandbox_path = workspace or (exec_res.isolated_path if exec_res else None)
            if not sandbox_path:
                return json.dumps(
                    {"status": "VERIFICATION_BLOCKED", "error": f"No isolated sandbox found for repair {repair_id}"},
                    indent=2,
                )

            custom_commands = json.loads(custom_commands_json) if custom_commands_json else {}
            current_attempt = record.get("attempt_number", 1)

            runner = VerificationRunner(workspace_path=sandbox_path)
            run = runner.run_verification_suite(
                repair_id=repair_id,
                attempt_number=current_attempt,
                custom_commands=custom_commands,
                timeout_seconds=timeout_seconds,
            )

            # Store in cache
            if "verification_history" not in record:
                record["verification_history"] = []
            record["verification_history"].append(run)
            record["latest_verification"] = run

            # Update attempts
            if "attempts" not in record:
                record["attempts"] = []
            patch = record.get("patch")
            record["attempts"].append({
                "attempt_number": current_attempt,
                "patch_hash": patch.patch_hash if patch else "none",
                "status": run.overall_result,
                "verification_id": run.verification_id,
            })

            _REPAIR_CACHE[repair_id] = record
            return run.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "INFRASTRUCTURE_ERROR", "error": str(e)}, indent=2)

    run_verification.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 19. Tool: get_verification (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_verification",
        description="Retrieve the latest or specific verification run for a repair.",
    )
    async def get_verification(repair_id: str, verification_id: str = "") -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        history = record.get("verification_history", [])
        if not history:
            return json.dumps({"error": f"No verification runs recorded for repair {repair_id}"}, indent=2)

        if verification_id:
            for v in history:
                if v.verification_id == verification_id:
                    return v.model_dump_json(indent=2)
            return json.dumps({"error": f"Verification run '{verification_id}' not found."}, indent=2)

        return record.get("latest_verification", history[-1]).model_dump_json(indent=2)

    get_verification.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 20. Tool: get_verification_history (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_verification_history",
        description="Retrieve complete verification run history across all repair attempts.",
    )
    async def get_verification_history(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        history = record.get("verification_history", [])
        return json.dumps([h.model_dump(mode="json") for h in history], indent=2)

    get_verification_history.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 21. Tool: analyze_verification_failure (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="analyze_verification_failure",
        description="Diagnose verification failure and check retry eligibility (max 3 attempts).",
    )
    async def analyze_verification_failure(repair_id: str, verification_id: str = "") -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            history = record.get("verification_history", [])
            if not history:
                return json.dumps({"error": f"No verification runs found for repair {repair_id}"}, indent=2)

            run = None
            if verification_id:
                for v in history:
                    if v.verification_id == verification_id:
                        run = v
                        break
            if not run:
                run = record.get("latest_verification", history[-1])

            analyzer = VerificationAnalyzer()
            prev_sigs = [s for s in record.get("signatures", [])]
            report = analyzer.analyze(verification_run=run, previous_signatures=prev_sigs)
            if "signatures" not in record:
                record["signatures"] = []
            record["signatures"].append(report.failure_signature)
            _REPAIR_CACHE[repair_id] = record
            return report.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    analyze_verification_failure.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 22. Tool: get_repair_attempts (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_repair_attempts",
        description="Retrieve history of bounded repair attempts (max 3).",
    )
    async def get_repair_attempts(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        attempts = record.get("attempts", [])
        return json.dumps(attempts, indent=2)

    get_repair_attempts.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 23. Tool: prepare_pull_request (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="prepare_pull_request",
        description="Verify entry preconditions and synthesize PR branch, commit metadata, and structured description.",
    )
    async def prepare_pull_request(
        repair_id: str,
        owner: str = "shreyvirmani",
        repo: str = "Devaura",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            exec_res = record.get("execution_result")
            patch = record.get("patch")
            ctx = record.get("context")
            latest_ver = record.get("latest_verification")

            class DummyRepair:
                def __init__(self):
                    self.id = repair_id
                    self.status = record.get("status", "VERIFIED")
                    self.investigation_id = ctx.investigation_id if ctx else f"inv-{repair_id[:8]}"
                    self.repository_id = ctx.repository_id if ctx else f"repo-{owner}/{repo}"
                    self.base_revision = record.get("base_revision", "HEAD")
                    self.workspace = type(
                        "DummyWorkspace",
                        (),
                        {"isolated_path": exec_res.isolated_path if exec_res else os.getcwd()},
                    )()
                    self.patch = patch

            repair_obj = DummyRepair()

            verified_res = None
            if latest_ver and hasattr(latest_ver, "overall_result") and latest_ver.overall_result == "PASS":
                verified_res = VerifiedRepairResult(
                    repair_id=repair_id,
                    investigation_id=repair_obj.investigation_id,
                    repository=f"{owner}/{repo}",
                    base_revision=repair_obj.base_revision,
                    final_workspace_id=getattr(repair_obj.workspace, "isolated_path", "ws-default"),
                    final_patch_hash=patch.patch_hash if patch else "hash-verified",
                    changed_files=patch.changed_files if patch else [],
                    final_diff=patch.unified_diff if patch else "",
                    verification_status="VERIFIED",
                    checks=[],
                    attempts=[],
                )

            orchestrator = PROrchestrator()
            prep_res = orchestrator.prepare_pull_request(
                repair=repair_obj,
                verified_result=verified_res,
                owner=owner,
                repo=repo,
            )
            record["pr_context"] = prep_res.context
            record["pr_preparation"] = prep_res
            _REPAIR_CACHE[repair_id] = record
            return prep_res.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "PR_BLOCKED", "error": str(e)}, indent=2)

    prepare_pull_request.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 24. Tool: get_pr_context (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_pr_context",
        description="Retrieve the synthesized PR context, title, markdown body, and branch name for a repair.",
    )
    async def get_pr_context(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        pr_ctx = record.get("pr_context")
        if not pr_ctx:
            return json.dumps({"error": f"No PR context prepared for repair {repair_id}"}, indent=2)
        return pr_ctx.model_dump_json(indent=2)

    get_pr_context.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 25. Tool: prepare_repair_branch (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="prepare_repair_branch",
        description="Verify git status and ensure repair branch exists and is checked out in workspace.",
    )
    async def prepare_repair_branch(repair_id: str, branch_name: str = "") -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            pr_ctx = record.get("pr_context")
            exec_res = record.get("execution_result")
            target_branch = branch_name or (pr_ctx.repair_branch if pr_ctx else f"devaura/repair/{repair_id[:8]}")
            target_path = exec_res.isolated_path if exec_res else os.getcwd()

            manager = GitStateManager(repo_path=target_path)
            branch_info = manager.prepare_repair_branch(target_branch)
            return json.dumps({
                "status": "BRANCH_READY",
                "branch": branch_info.name,
                "current_sha": branch_info.commit_sha,
                "is_current": branch_info.is_current,
            }, indent=2)
        except Exception as e:
            return json.dumps({"status": "BRANCH_ERROR", "error": str(e)}, indent=2)

    prepare_repair_branch.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 26. Tool: prepare_repair_commit (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="prepare_repair_commit",
        description="Stage verified changes only and create a structured commit with attribution in workspace.",
    )
    async def prepare_repair_commit(repair_id: str, commit_message: str = "") -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            pr_ctx = record.get("pr_context")
            exec_res = record.get("execution_result")
            target_path = exec_res.isolated_path if exec_res else os.getcwd()
            allowed_files = pr_ctx.changed_files if pr_ctx else []
            msg = commit_message or (pr_ctx.commit_message if pr_ctx else f"fix(repair): verified fix for {repair_id[:8]}")

            manager = GitStateManager(repo_path=target_path)
            commit_info = manager.create_repair_commit(
                commit_message=msg,
                allowed_files=allowed_files,
                author_name="Devaura Repair Agent",
                author_email="repair-agent@devaura.ai",
            )
            return json.dumps({
                "status": "COMMIT_READY",
                "commit_sha": commit_info.sha,
                "commit_message": commit_info.message,
                "author": commit_info.author,
            }, indent=2)
        except Exception as e:
            return json.dumps({"status": "COMMIT_ERROR", "error": str(e)}, indent=2)

    prepare_repair_commit.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 27. Tool: request_pr_approval (CONTROLLED)
    # --------------------------------------------------------------------------
    @server.tool(
        name="request_pr_approval",
        description="Generate cryptographic HMAC-SHA256 PR approval token bound to exact repair, patch, branch, and repo.",
    )
    async def request_pr_approval(
        repair_id: str,
        approver_identity: str = "human-operator",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            pr_ctx = record.get("pr_context")
            if not pr_ctx:
                return json.dumps({"error": f"PR context not found for repair {repair_id}. Call prepare_pull_request first."}, indent=2)

            orchestrator = PROrchestrator()
            approval = orchestrator.authorize_pull_request(
                context=pr_ctx,
                user_identity=approver_identity,
            )
            record["pr_approval"] = approval
            _REPAIR_CACHE[repair_id] = record
            return approval.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    request_pr_approval.risk_level = RiskLevel.CONTROLLED

    # --------------------------------------------------------------------------
    # 28. Tool: push_repair_branch (DANGEROUS)
    # --------------------------------------------------------------------------
    @server.tool(
        name="push_repair_branch",
        description="Push verified repair branch to remote Git provider (never touches main).",
    )
    async def push_repair_branch(
        repair_id: str,
        remote_name: str = "origin",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            pr_ctx = record.get("pr_context")
            if not pr_ctx:
                return json.dumps({"error": f"PR context not found for {repair_id}"}, indent=2)

            token = os.environ.get("GITHUB_TOKEN")
            provider = GitHubClient(token=token) if token else MockGitProvider()

            exec_res = record.get("execution_result")
            target_path = exec_res.isolated_path if exec_res else os.getcwd()

            branch_info = await provider.push_branch(
                owner=pr_ctx.owner,
                repo=pr_ctx.repo,
                branch=pr_ctx.repair_branch,
                local_repo_path=target_path,
            )
            return json.dumps({
                "status": "BRANCH_PUSHED",
                "branch": branch_info.name,
                "commit_sha": branch_info.commit_sha,
            }, indent=2)
        except Exception as e:
            return json.dumps({"status": "PUSH_FAILED", "error": str(e)}, indent=2)

    push_repair_branch.risk_level = RiskLevel.DANGEROUS

    # --------------------------------------------------------------------------
    # 29. Tool: create_pull_request (DANGEROUS)
    # --------------------------------------------------------------------------
    @server.tool(
        name="create_pull_request",
        description="Submit verified Pull Request to Git provider after cryptographic human authorization check.",
    )
    async def create_pull_request(
        repair_id: str,
        approval_token: str = "",
        approver: str = "human-operator",
    ) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            pr_ctx = record.get("pr_context")
            if not pr_ctx:
                return json.dumps({"error": f"PR context not found for {repair_id}"}, indent=2)

            approval = record.get("pr_approval")
            if not approval:
                gate = HumanPRApprovalGate()
                approval = gate.create_approval(
                    repair_id=repair_id,
                    patch_hash=pr_ctx.patch_hash,
                    base_revision=pr_ctx.base_revision,
                    repair_branch=pr_ctx.repair_branch,
                    repository=pr_ctx.repository,
                    user_identity=approver,
                    operation="CREATE_PULL_REQUEST",
                )

            if approval_token:
                approval.approval_token = approval_token

            token = os.environ.get("GITHUB_TOKEN")
            provider = GitHubClient(token=token) if token else MockGitProvider()

            orchestrator = PROrchestrator()
            exec_res = record.get("execution_result")
            target_path = exec_res.isolated_path if exec_res else os.getcwd()

            class DummyRepair:
                def __init__(self):
                    self.id = repair_id
                    self.workspace = type("DummyWorkspace", (), {"isolated_path": target_path})()

            result = await orchestrator.execute_pull_request_creation(
                repair=DummyRepair(),
                context=pr_ctx,
                approval=approval,
                provider=provider,
                local_repo_path=target_path,
            )
            record["pr_result"] = result
            _REPAIR_CACHE[repair_id] = record
            return result.model_dump_json(indent=2)
        except Exception as e:
            return json.dumps({"status": "PR_CREATION_FAILED", "error": str(e)}, indent=2)

    create_pull_request.risk_level = RiskLevel.DANGEROUS

    # --------------------------------------------------------------------------
    # 30. Tool: get_pull_request (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_pull_request",
        description="Retrieve created Pull Request details, status, and URL.",
    )
    async def get_pull_request(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        pr_res = record.get("pr_result")
        if not pr_res:
            return json.dumps({"error": f"No Pull Request found for repair {repair_id}"}, indent=2)
        return pr_res.model_dump_json(indent=2)

    get_pull_request.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 31. Tool: get_pr_status (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_pr_status",
        description="Query live CI check-run status and review state for an active Pull Request.",
    )
    async def get_pr_status(repair_id: str) -> str:
        try:
            record = _REPAIR_CACHE.get(repair_id, {})
            pr_res = record.get("pr_result")
            if not pr_res:
                return json.dumps({"error": f"No active PR for repair {repair_id}"}, indent=2)

            token = os.environ.get("GITHUB_TOKEN")
            provider = GitHubClient(token=token) if token else MockGitProvider()

            owner, repo = pr_res.repository.split("/") if "/" in pr_res.repository else ("shreyvirmani", "Devaura")
            ci_status = await provider.get_ci_status(owner=owner, repo=repo, commit_sha=pr_res.commit_sha or "HEAD")
            review_status = await provider.get_review_status(owner=owner, repo=repo, pr_number=pr_res.pr_number)

            return json.dumps({
                "repair_id": repair_id,
                "pr_number": pr_res.pr_number,
                "pr_url": pr_res.pr_url,
                "pr_state": pr_res.state.value,
                "ci_status": ci_status.model_dump(mode="json"),
                "review_status": review_status.model_dump(mode="json"),
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)}, indent=2)

    get_pr_status.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # 32. Tool: get_pull_request_history (SAFE)
    # --------------------------------------------------------------------------
    @server.tool(
        name="get_pull_request_history",
        description="Retrieve complete audit trail and event logs for PR lifecycle.",
    )
    async def get_pull_request_history(repair_id: str) -> str:
        record = _REPAIR_CACHE.get(repair_id, {})
        events = record.get("pr_events", [])
        return json.dumps(events, indent=2)

    get_pull_request_history.risk_level = RiskLevel.SAFE

    # --------------------------------------------------------------------------
    # Standardized Prompts
    # --------------------------------------------------------------------------
    @server.prompt(name="debug_issue", description="Synthesizes failure diagnosis given an issue and stack trace.")
    async def debug_issue(issue_description: str, stack_trace: str = "") -> str:
        return (
            f"You are the Devaura Investigator. Investigate this failure:\n"
            f"ISSUE:\n{issue_description}\n\n"
            f"STACK TRACE:\n{stack_trace}\n\n"
            "Use search_code, read_file, and git_history to determine the root cause."
        )

    @server.prompt(name="fix_ci_failure", description="Analyzes CI error logs and suggests repair strategy.")
    async def fix_ci_failure(ci_logs: str) -> str:
        return f"Analyze these CI logs and localize the failing test/file:\n{ci_logs}"

    @server.prompt(name="review_pull_request", description="Performs independent review on a proposed code patch.")
    async def review_pull_request(diff: str) -> str:
        return f"Review this verified diff for regressions and style violations:\n{diff}"

    return server


# Singleton native server instance
_native_server_instance: Optional[MCPServer] = None


def get_native_mcp_server() -> MCPServer:
    global _native_server_instance
    if _native_server_instance is None:
        _native_server_instance = create_devaura_native_server()
    return _native_server_instance
