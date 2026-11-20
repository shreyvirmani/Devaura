"""Devaura Verification Output Normalizer.

Converts raw process outputs from tests, linters, and type checkers into
structured TestFailure objects and computes deterministic failure signatures.
"""

import hashlib
import re
from typing import List, Optional, Tuple

from agent.repair.models import CheckType, FailureSignature, TestFailure


class OutputNormalizer:
    """Parses raw test, lint, and typecheck outputs into normalized failure structures."""

    PYTEST_FAILED_PATTERN = re.compile(
        r"FAILED\s+([^\s:]+)::([^\s\-]+)(?:\s+-\s+(.+))?"
    )
    TRACEBACK_FILE_LINE_PATTERN = re.compile(
        r'File\s+["\']([^"\']+)["\'],\s+line\s+(\d+)(?:,\s+in\s+([^\n]+))?'
    )
    PYTHON_EXCEPTION_PATTERN = re.compile(
        r"^(?:[a-zA-Z_][a-zA-Z0-9_\.]*\.)?([A-Z][a-zA-Z0-9_]*Error|[A-Z][a-zA-Z0-9_]*Exception):\s*(.*)$",
        re.MULTILINE,
    )
    MYPY_ERROR_PATTERN = re.compile(
        r"^([^:\n]+):(\d+)(?::\d+)?:?\s+error:\s+(.+)$",
        re.MULTILINE,
    )
    LINT_ERROR_PATTERN = re.compile(
        r"^([^:\n]+):(\d+):(?:\d+:)?\s+([A-Z]\d+|[A-Z]+[0-9]+|\w+)\s+(.+)$",
        re.MULTILINE,
    )
    TS_COMPILER_ERROR_PATTERN = re.compile(
        r"^([^(:\n]+)(?:\((\d+),\d+\))?:\s+error\s+(TS\d+):\s+(.+)$",
        re.MULTILINE,
    )
    JEST_FAIL_PATTERN = re.compile(
        r"●\s+([^\n]+)\s*\n\s+([A-Z][a-zA-Z0-9_]*Error|[A-Za-z]+Error):\s*(.+)"
    )

    @classmethod
    def parse_test_output(
        cls, stdout: str, stderr: str, check_type: CheckType = CheckType.TESTS
    ) -> List[TestFailure]:
        """Extract structured test failures from test execution output."""
        failures: List[TestFailure] = []
        combined = (stdout or "") + "\n" + (stderr or "")

        # 1. Pytest Failure Lines
        for match in cls.PYTEST_FAILED_PATTERN.finditer(combined):
            file_path = match.group(1).strip()
            test_name = match.group(2).strip()
            err_msg = match.group(3).strip() if match.group(3) else "Test assertion failed"

            # Try to extract exception type and line
            line_no = None
            err_type = "AssertionError"
            exc_m = cls.PYTHON_EXCEPTION_PATTERN.search(err_msg)
            if exc_m:
                err_type = exc_m.group(1)
                err_msg = exc_m.group(2) or err_msg

            # Check for stack frames for this file
            for tb_match in cls.TRACEBACK_FILE_LINE_PATTERN.finditer(combined):
                tb_file = tb_match.group(1).replace("\\", "/")
                if file_path.replace("\\", "/") in tb_file or tb_file in file_path.replace("\\", "/"):
                    line_no = int(tb_match.group(2))

            failures.append(
                TestFailure(
                    test_name=test_name,
                    file=file_path,
                    line=line_no,
                    error_type=err_type,
                    message=err_msg,
                    traceback=combined[:2000],
                )
            )

        # 2. Jest / Node Test Failures
        if not failures:
            for jmatch in cls.JEST_FAIL_PATTERN.finditer(combined):
                failures.append(
                    TestFailure(
                        test_name=jmatch.group(1).strip(),
                        file="unknown_test.js",
                        line=None,
                        error_type=jmatch.group(2).strip(),
                        message=jmatch.group(3).strip(),
                        traceback=combined[:2000],
                    )
                )

        # 3. Python General Traceback / Exception fallback
        if not failures:
            tb_matches = list(cls.TRACEBACK_FILE_LINE_PATTERN.finditer(combined))
            exc_match = cls.PYTHON_EXCEPTION_PATTERN.search(combined)
            if exc_match and tb_matches:
                last_tb = tb_matches[-1]
                failures.append(
                    TestFailure(
                        test_name=last_tb.group(3) or "unnamed_block",
                        file=last_tb.group(1),
                        line=int(last_tb.group(2)),
                        error_type=exc_match.group(1),
                        message=exc_match.group(2).strip(),
                        traceback=combined[:2000],
                    )
                )

        # 4. Fallback: If non-empty output and indicated failure, produce UNPARSED_FAILURE
        if not failures and combined.strip() and ("fail" in combined.lower() or "error" in combined.lower()):
            failures.append(
                TestFailure(
                    test_name="unparsed_test",
                    file="unknown",
                    line=None,
                    error_type="UNPARSED_FAILURE",
                    message=combined.strip()[:300],
                    traceback=combined[:2000],
                )
            )

        return failures

    @classmethod
    def parse_lint_output(cls, stdout: str, stderr: str) -> List[TestFailure]:
        """Extract structured errors from ruff/flake8/eslint outputs."""
        failures: List[TestFailure] = []
        combined = (stdout or "") + "\n" + (stderr or "")

        for match in cls.LINT_ERROR_PATTERN.finditer(combined):
            failures.append(
                TestFailure(
                    test_name="lint_check",
                    file=match.group(1).strip(),
                    line=int(match.group(2)),
                    error_type=match.group(3).strip(),
                    message=match.group(4).strip(),
                )
            )

        if not failures and combined.strip() and ("error" in combined.lower() or "violation" in combined.lower()):
            failures.append(
                TestFailure(
                    test_name="lint_check",
                    file="unknown",
                    line=None,
                    error_type="UNPARSED_FAILURE",
                    message=combined.strip()[:300],
                )
            )

        return failures

    @classmethod
    def parse_typecheck_output(cls, stdout: str, stderr: str) -> List[TestFailure]:
        """Extract structured errors from mypy or tsc outputs."""
        failures: List[TestFailure] = []
        combined = (stdout or "") + "\n" + (stderr or "")

        # Mypy errors
        for match in cls.MYPY_ERROR_PATTERN.finditer(combined):
            failures.append(
                TestFailure(
                    test_name="typecheck",
                    file=match.group(1).strip(),
                    line=int(match.group(2)),
                    error_type="TypeError",
                    message=match.group(3).strip(),
                )
            )

        # TS Compiler errors
        for match in cls.TS_COMPILER_ERROR_PATTERN.finditer(combined):
            failures.append(
                TestFailure(
                    test_name="typecheck",
                    file=match.group(1).strip(),
                    line=int(match.group(2)) if match.group(2) else None,
                    error_type=match.group(3).strip(),
                    message=match.group(4).strip(),
                )
            )

        if not failures and combined.strip() and "error" in combined.lower():
            failures.append(
                TestFailure(
                    test_name="typecheck",
                    file="unknown",
                    line=None,
                    error_type="UNPARSED_FAILURE",
                    message=combined.strip()[:300],
                )
            )

        return failures

    @classmethod
    def compute_failure_signature(
        cls,
        check_type: CheckType,
        failure: TestFailure,
    ) -> FailureSignature:
        """Compute deterministic SHA-256 fingerprint of a failure."""
        norm_file = failure.file.replace("\\", "/").lower()
        norm_line = str(failure.line or "")
        norm_test = (failure.test_name or "").lower()
        norm_err = re.sub(r"\s+", " ", (failure.message or failure.error_type).strip().lower())

        signature_raw = f"{check_type.value}:{norm_err}:{norm_file}:{norm_line}:{norm_test}"
        sig_hash = hashlib.sha256(signature_raw.encode("utf-8")).hexdigest()

        return FailureSignature(
            signature_hash=sig_hash,
            check_type=check_type.value,
            error_summary=failure.message or failure.error_type,
            file_path=norm_file,
            line_number=failure.line,
            test_name=failure.test_name,
        )
