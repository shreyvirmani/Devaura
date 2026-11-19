import json
import os
import re
import subprocess
from pathlib import Path
from typing import List, Optional, Set
from code_intelligence.models import SearchMatch

_DEFAULT_IGNORED_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    ".pytest_cache",
    "dist",
    "build",
    ".gemini",
}

_CODE_EXTENSIONS: Set[str] = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".toml",
    ".sql",
    ".html",
    ".css",
}


class RipgrepSearch:
    """Tier 1: Fast regex/string search using ripgrep CLI with Python fallback."""

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def search(
        self,
        query: str,
        path_filter: Optional[str] = None,
        max_results: int = 25,
        case_sensitive: bool = False,
    ) -> List[SearchMatch]:
        if not query or not query.strip():
            return []

        search_dir = self.workspace_root
        if path_filter:
            target = (self.workspace_root / path_filter).resolve()
            if target.exists() and str(target).startswith(str(self.workspace_root)):
                search_dir = target

        matches: List[SearchMatch] = []

        # 1. Try Ripgrep CLI if available
        try:
            cmd = ["rg", "--json", "-m", str(max_results)]
            if not case_sensitive:
                cmd.append("-i")
            cmd.extend(["--", query, str(search_dir)])

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=8,
            )
            if proc.returncode in (0, 1) and proc.stdout:
                for line in proc.stdout.splitlines():
                    try:
                        record = json.loads(line)
                        if record.get("type") == "match":
                            data = record.get("data", {})
                            raw_file = data.get("path", {}).get("text", "")
                            rel_file = os.path.relpath(raw_file, str(self.workspace_root)).replace("\\", "/")
                            line_num = data.get("line_number", 1)
                            matched_text = data.get("lines", {}).get("text", "").strip()
                            matches.append(
                                SearchMatch(
                                    tier="ripgrep",
                                    file=rel_file,
                                    line=line_num,
                                    column=1,
                                    text=matched_text,
                                    score=1.0,
                                )
                            )
                            if len(matches) >= max_results:
                                return matches
                    except json.JSONDecodeError:
                        continue
                if matches:
                    return matches
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

        # 2. Python Fallback Walker
        return self._python_search_fallback(query, search_dir, max_results, case_sensitive)

    def _python_search_fallback(
        self,
        query: str,
        search_dir: Path,
        max_results: int,
        case_sensitive: bool,
    ) -> List[SearchMatch]:
        matches: List[SearchMatch] = []
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            pattern = re.compile(re.escape(query), flags)
        except re.error:
            pattern = re.compile(re.escape(query))

        target_files = [search_dir] if search_dir.is_file() else []
        if not target_files:
            for root, dirs, files in os.walk(search_dir):
                dirs[:] = [d for d in dirs if d not in _DEFAULT_IGNORED_DIRS]
                for f in files:
                    ext = Path(f).suffix.lower()
                    if ext in _CODE_EXTENSIONS or not ext:
                        target_files.append(Path(root) / f)

        for file_path in target_files:
            try:
                rel_path = os.path.relpath(file_path, str(self.workspace_root)).replace("\\", "/")
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_idx, line in enumerate(f, start=1):
                        match = pattern.search(line)
                        if match:
                            matches.append(
                                SearchMatch(
                                    tier="ripgrep",
                                    file=rel_path,
                                    line=line_idx,
                                    column=match.start() + 1,
                                    text=line.strip(),
                                    score=0.9,
                                )
                            )
                            if len(matches) >= max_results:
                                return matches
            except Exception:
                continue

        return matches
