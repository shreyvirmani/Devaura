import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.api.logger import logger, redact_secrets
from mcp.models import RiskLevel
from mcp.policy import policy_engine
from mcp.server.mcpserver import MCPServer


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
        description="Search repository source code for keyword or regex matches.",
    )
    async def search_code(
        query: str,
        path: str = ".",
        max_results: int = 20,
        workspace: str = ".",
    ) -> str:
        """Searches files inside the workspace with result limits."""
        search_root = policy_engine.validate_workspace_path(workspace, path)
        if not search_root.exists():
            return f"Error: Search directory '{path}' does not exist."

        # Attempt fast ripgrep if installed
        matches: List[Dict[str, Any]] = []
        try:
            rg_cmd = ["rg", "--json", "-m", str(max_results), "--", query, str(search_root)]
            proc = subprocess.run(rg_cmd, capture_output=True, text=True, timeout=10)
            if proc.returncode in (0, 1) and proc.stdout:
                for line in proc.stdout.splitlines():
                    try:
                        data = json.loads(line)
                        if data.get("type") == "match":
                            m = data.get("data", {})
                            rel_path = os.path.relpath(m.get("path", {}).get("text", ""), str(Path(workspace).resolve()))
                            line_num = m.get("line_number", 0)
                            match_text = m.get("lines", {}).get("text", "").strip()
                            matches.append({"file": rel_path, "line": line_num, "text": match_text})
                            if len(matches) >= max_results:
                                break
                    except json.JSONDecodeError:
                        continue
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

        # Python fallback search if ripgrep was unavailable or returned 0
        if not matches:
            regex = re.compile(re.escape(query), re.IGNORECASE)
            extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".json", ".md", ".yml", ".yaml", ".toml"}
            for root, dirs, files in os.walk(search_root):
                # Prune noisy directories
                dirs[:] = [d for d in dirs if d not in {".git", ".venv", "node_modules", "__pycache__", ".next"}]
                for file in files:
                    if any(file.endswith(ext) for ext in extensions):
                        file_path = Path(root) / file
                        rel_path = os.path.relpath(file_path, str(Path(workspace).resolve()))
                        try:
                            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                for idx, line_text in enumerate(f, start=1):
                                    if regex.search(line_text):
                                        matches.append({"file": rel_path, "line": idx, "text": line_text.strip()})
                                        if len(matches) >= max_results:
                                            break
                        except Exception:
                            continue
                    if len(matches) >= max_results:
                        break
                if len(matches) >= max_results:
                    break

        if not matches:
            return f"No code occurrences found for query '{query}' in '{path}'."

        result_str = f"Found {len(matches)} matches for '{query}':\n"
        for m in matches:
            result_str += f"{m['file']}:{m['line']} -> {m['text']}\n"
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
        target_name = Path(target_file).stem
        candidates: List[str] = []

        # Look for test_*.py or *.test.ts
        patterns = [
            f"test_{target_name}.py",
            f"{target_name}_test.py",
            f"{target_name}.test.ts",
            f"{target_name}.spec.ts",
            f"{target_name}.test.js",
        ]

        for p in patterns:
            for match in base.glob(f"**/{p}"):
                rel = os.path.relpath(match, base)
                if rel not in candidates:
                    candidates.append(rel)

        # General test directory fallback
        if not candidates:
            for test_file in base.glob("tests/**/test_*.py"):
                candidates.append(os.path.relpath(test_file, base))

        if not candidates:
            return f"No related tests discovered for '{target_file}'."
        return json.dumps({"target": target_file, "related_tests": candidates}, indent=2)

    find_related_tests.risk_level = RiskLevel.SAFE

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
