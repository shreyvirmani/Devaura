"""Devaura Sandbox Verification Runner.

Executes tests, linters, and type checkers strictly inside the isolated
sandbox workspace under safe execution policies and resource limits.
"""

import os
import shlex
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.repair.models import (
    CheckStatus,
    CheckType,
    OverallVerificationStatus,
    VerificationCheck,
    VerificationRun,
)
from agent.verification.normalizer import OutputNormalizer
from apps.api.logger import logger, redact_secrets
from mcp.policy.policy_engine import ALLOWED_COMMANDS, DISALLOWED_SHELL_PATTERNS


class VerificationSecurityError(PermissionError):
    """Raised when an unsafe command or path is attempted for verification."""
    pass


class VerificationRunner:
    """Executes sandboxed verification checks and normalizes results."""

    MAX_OUTPUT_BYTES = 50 * 1024  # 50 KB output limit
    DEFAULT_TIMEOUT_SECONDS = 30

    def __init__(
        self,
        workspace_path: str,
        source_repo_root: Optional[str] = None,
    ):
        self.workspace_path = os.path.abspath(workspace_path)
        self.source_repo_root = os.path.abspath(source_repo_root) if source_repo_root else None

    def validate_sandbox_isolation(self) -> None:
        """Ensure verification runs exclusively in an isolated sandbox, never original repo."""
        if not os.path.exists(self.workspace_path):
            raise VerificationSecurityError(f"Sandbox workspace does not exist: {self.workspace_path}")

        if ".." in self.workspace_path:
            raise VerificationSecurityError(f"Path traversal detected in workspace path: {self.workspace_path}")

        if self.source_repo_root:
            if os.path.samefile(self.workspace_path, self.source_repo_root):
                raise VerificationSecurityError(
                    "Security Violation: Attempted to run verification on original repository instead of sandbox!"
                )

    def validate_command(self, command: str) -> List[str]:
        """Validate command against security allowlist and shell operator blacklist."""
        for pattern in DISALLOWED_SHELL_PATTERNS:
            if pattern.search(command):
                raise VerificationSecurityError(
                    f"Security: Command contains forbidden shell operator or pattern: '{command}'"
                )

        try:
            tokens = shlex.split(command, posix=True)
        except Exception as e:
            raise VerificationSecurityError(f"Failed to parse verification command: {e}")

        if not tokens:
            raise VerificationSecurityError("Empty verification command.")

        executable = Path(tokens[0]).stem.lower()
        if executable not in ALLOWED_COMMANDS and executable != "pytest" and executable != "python":
            raise VerificationSecurityError(
                f"Security: Executable '{executable}' is not in approved verification allowlist: {ALLOWED_COMMANDS}"
            )

        return tokens

    def run_check(
        self,
        check_type: CheckType,
        command: str,
        timeout_seconds: Optional[int] = None,
    ) -> VerificationCheck:
        """Execute a single check inside the sandbox under resource limits."""
        timeout = timeout_seconds or self.DEFAULT_TIMEOUT_SECONDS
        start_time = time.perf_counter()

        try:
            self.validate_sandbox_isolation()
            tokens = self.validate_command(command)
        except VerificationSecurityError as se:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return VerificationCheck(
                check_type=check_type,
                command=command,
                status=CheckStatus.BLOCKED,
                exit_code=-1,
                duration_ms=duration_ms,
                stderr=str(se),
            )

        try:
            proc = subprocess.run(
                tokens,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            stdout = redact_secrets(proc.stdout[: self.MAX_OUTPUT_BYTES])
            stderr = redact_secrets(proc.stderr[: self.MAX_OUTPUT_BYTES])

            if proc.returncode == 0:
                status = CheckStatus.PASSED
                parsed_errors = []
            else:
                status = CheckStatus.FAILED
                if check_type == CheckType.TESTS:
                    parsed_errors = OutputNormalizer.parse_test_output(stdout, stderr, check_type)
                elif check_type == CheckType.LINT:
                    parsed_errors = OutputNormalizer.parse_lint_output(stdout, stderr)
                else:
                    parsed_errors = OutputNormalizer.parse_typecheck_output(stdout, stderr)

            return VerificationCheck(
                check_type=check_type,
                command=command,
                status=status,
                exit_code=proc.returncode,
                duration_ms=duration_ms,
                stdout=stdout,
                stderr=stderr,
                parsed_errors=parsed_errors,
                resource_usage={"duration_ms": duration_ms, "timeout_seconds": timeout},
            )

        except FileNotFoundError as fnf:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return VerificationCheck(
                check_type=check_type,
                command=command,
                status=CheckStatus.INFRASTRUCTURE_ERROR,
                exit_code=127,
                duration_ms=duration_ms,
                stderr=f"Infrastructure Error: Required executable missing: {fnf}",
                resource_usage={"duration_ms": duration_ms, "error": "executable_not_found"},
            )
        except subprocess.TimeoutExpired:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return VerificationCheck(
                check_type=check_type,
                command=command,
                status=CheckStatus.TIMEOUT,
                exit_code=124,
                duration_ms=duration_ms,
                stderr=f"Resource Limit: Command timed out after {timeout} seconds.",
                resource_usage={"duration_ms": duration_ms, "timed_out": True},
            )
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return VerificationCheck(
                check_type=check_type,
                command=command,
                status=CheckStatus.INFRASTRUCTURE_ERROR,
                exit_code=-1,
                duration_ms=duration_ms,
                stderr=f"Execution error: {e}",
            )

    def run_verification_suite(
        self,
        repair_id: str,
        attempt_number: int = 1,
        custom_commands: Optional[Dict[str, str]] = None,
        timeout_seconds: Optional[int] = None,
    ) -> VerificationRun:
        """Run full verification suite (tests, linter, typecheck) inside sandbox."""
        verification_id = str(uuid.uuid4())
        workspace_id = os.path.basename(self.workspace_path)
        commands = custom_commands or {}

        # Default commands
        test_cmd = commands.get("tests") or "pytest -q"
        lint_cmd = commands.get("lint") or "ruff check ."
        typecheck_cmd = commands.get("typecheck") or "mypy ."

        checks: List[VerificationCheck] = []

        # 1. Tests
        test_check = self.run_check(CheckType.TESTS, test_cmd, timeout_seconds)
        checks.append(test_check)

        # 2. Linter
        lint_check = self.run_check(CheckType.LINT, lint_cmd, timeout_seconds)
        checks.append(lint_check)

        # 3. Typechecker
        typecheck_check = self.run_check(CheckType.TYPECHECK, typecheck_cmd, timeout_seconds)
        checks.append(typecheck_check)

        # Determine overall status
        any_infra = any(c.status == CheckStatus.INFRASTRUCTURE_ERROR for c in checks)
        any_blocked = any(c.status == CheckStatus.BLOCKED for c in checks)
        any_failed = any(c.status in {CheckStatus.FAILED, CheckStatus.TIMEOUT} for c in checks)
        all_passed = all(c.status == CheckStatus.PASSED for c in checks)

        if all_passed:
            overall_status = OverallVerificationStatus.PASSED
            overall_result = "PASSED"
        elif any_blocked:
            overall_status = OverallVerificationStatus.BLOCKED
            overall_result = "BLOCKED"
        elif any_infra:
            overall_status = OverallVerificationStatus.INFRASTRUCTURE_ERROR
            overall_result = "INFRASTRUCTURE_ERROR"
        elif any_failed:
            overall_status = OverallVerificationStatus.FAILED
            overall_result = "FAILED"
        else:
            overall_status = OverallVerificationStatus.PARTIAL
            overall_result = "PARTIAL"

        return VerificationRun(
            verification_id=verification_id,
            repair_id=repair_id,
            attempt_number=attempt_number,
            workspace_id=workspace_id,
            status=overall_status,
            checks=checks,
            overall_result=overall_result,
        )
