"""Deterministic Stack Trace Parser.

Parses stack traces from Python, Pytest, JavaScript/TypeScript, and standard
framework outputs into structured, normalized frame objects. Maps frames to
Code Intelligence symbols without fabricating unresolvable entities.
"""

import os
import re
from typing import List, Optional
from agent.models import ParsedStackFrame, ParsedStackTrace, ResolutionStatus


class StackTraceParser:
    """Parses raw error stack traces into structured frames and identifies failing lines."""

    # Python standard traceback regex:
    # File "app/service.py", line 42, in process_user
    PYTHON_FRAME_RE = re.compile(
        r'File\s+["\'](?P<file>[^"\']+)["\'],\s+line\s+(?P<line>\d+)(?:,\s+in\s+(?P<func>[^\n]+))?(?:\n\s+(?P<code>[^\n]+))?',
        re.MULTILINE,
    )

    # Pytest failure format:
    # tests/test_auth.py:25: in test_authenticate
    # > assert authenticate(...)
    PYTEST_FRAME_RE = re.compile(
        r'^(?P<file>[a-zA-Z0-9_\-\./\\]+\.py):(?P<line>\d+):\s+(?:in\s+(?P<func>[^\n]+))?',
        re.MULTILINE,
    )

    # JavaScript / Node / V8 stack trace format:
    # at UserService.processUser (frontend/user.ts:42:15)
    # at frontend/api.js:33:10
    JS_FRAME_RE = re.compile(
        r'at\s+(?:(?P<func>[^\s(]+)\s+\()?(?P<file>[a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+):(?P<line>\d+)(?::(?P<col>\d+))?\)?',
        re.MULTILINE,
    )

    # Exception summary line regex (e.g. TypeError: 'NoneType' object is not subscriptable)
    EXCEPTION_LINE_RE = re.compile(
        r'^(?P<type>[a-zA-Z0-9_]+(?:Error|Exception|Failure)?):\s*(?P<msg>.*)$',
        re.MULTILINE,
    )

    NON_APP_SUBSTRINGS = [
        "site-packages",
        ".venv",
        "venv",
        "node_modules",
        "<frozen",
        "<string>",
        "python3.",
        "lib/python",
    ]

    def parse(self, raw_trace: str, workspace_root: Optional[str] = None) -> ParsedStackTrace:
        """Parse raw stack trace text into a ParsedStackTrace model."""
        if not raw_trace or not raw_trace.strip():
            return ParsedStackTrace(raw_trace="", error_message="", frames=[])

        raw_trace_str = raw_trace.strip()
        frames: List[ParsedStackFrame] = []

        # 1. Try Python standard traceback
        for match in self.PYTHON_FRAME_RE.finditer(raw_trace_str):
            file_path = self._normalize_path(match.group("file"), workspace_root)
            line_no = int(match.group("line"))
            func_name = (match.group("func") or "<module>").strip()
            code_snippet = (match.group("code") or "").strip()

            is_app = not any(sub in file_path.lower() for sub in self.NON_APP_SUBSTRINGS)
            frames.append(
                ParsedStackFrame(
                    file=file_path,
                    line=line_no,
                    function=func_name,
                    code_context=code_snippet,
                    is_application_code=is_app,
                    resolution_status=ResolutionStatus.UNRESOLVED.value,
                )
            )

        # 2. Try Pytest format if no standard frames found
        if not frames:
            for match in self.PYTEST_FRAME_RE.finditer(raw_trace_str):
                file_path = self._normalize_path(match.group("file"), workspace_root)
                line_no = int(match.group("line"))
                func_name = (match.group("func") or "<test>").strip()

                is_app = not any(sub in file_path.lower() for sub in self.NON_APP_SUBSTRINGS)
                frames.append(
                    ParsedStackFrame(
                        file=file_path,
                        line=line_no,
                        function=func_name,
                        is_application_code=is_app,
                        resolution_status=ResolutionStatus.UNRESOLVED.value,
                    )
                )

        # 3. Try JS / TS format if still no frames found
        if not frames:
            for match in self.JS_FRAME_RE.finditer(raw_trace_str):
                file_path = self._normalize_path(match.group("file"), workspace_root)
                line_no = int(match.group("line"))
                func_name = (match.group("func") or "<anonymous>").strip()

                is_app = not any(sub in file_path.lower() for sub in self.NON_APP_SUBSTRINGS)
                frames.append(
                    ParsedStackFrame(
                        file=file_path,
                        line=line_no,
                        function=func_name,
                        is_application_code=is_app,
                        resolution_status=ResolutionStatus.UNRESOLVED.value,
                    )
                )

        # Extract Exception Type and Message
        exc_type = "UnknownException"
        exc_msg = ""
        exc_matches = list(self.EXCEPTION_LINE_RE.finditer(raw_trace_str))
        if exc_matches:
            last_match = exc_matches[-1]
            exc_type = last_match.group("type").strip()
            exc_msg = last_match.group("msg").strip()
        else:
            # Fallback: take last non-empty line
            lines = [l.strip() for l in raw_trace_str.splitlines() if l.strip()]
            if lines:
                last_line = lines[-1]
                if ":" in last_line:
                    parts = last_line.split(":", 1)
                    exc_type = parts[0].strip()
                    exc_msg = parts[1].strip()
                else:
                    exc_msg = last_line

        # Determine failing and caller frame
        failing_frame: Optional[ParsedStackFrame] = None
        caller_frame: Optional[ParsedStackFrame] = None

        app_frames = [f for f in frames if f.is_application_code]
        if app_frames:
            failing_frame = app_frames[-1]
            if len(app_frames) > 1:
                caller_frame = app_frames[-2]
        elif frames:
            failing_frame = frames[-1]
            if len(frames) > 1:
                caller_frame = frames[-2]

        return ParsedStackTrace(
            raw_trace=raw_trace_str,
            exception_type=exc_type,
            error_message=exc_msg,
            frames=frames,
            failing_frame=failing_frame,
            caller_frame=caller_frame,
        )

    def _normalize_path(self, raw_path: str, workspace_root: Optional[str]) -> str:
        """Normalize file path to workspace-relative forward-slash path."""
        p = raw_path.replace("\\", "/")
        if workspace_root:
            w = workspace_root.replace("\\", "/").rstrip("/")
            if p.startswith(w):
                p = p[len(w):].lstrip("/")
        return p
