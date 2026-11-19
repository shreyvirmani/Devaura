import fnmatch
import os
from pathlib import Path
from typing import List, Optional, Set
from code_intelligence.models import SearchMatch

_IGNORE_DIRS: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".next",
    ".pytest_cache",
    "dist",
    "build",
}


class PathSearch:
    """Tier 3: Repository path and file metadata search supporting glob and prefix matching."""

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()

    def search(
        self,
        query: str,
        max_results: int = 25,
        extension: Optional[str] = None,
    ) -> List[SearchMatch]:
        if not query or not query.strip():
            return []

        clean_query = query.strip()
        is_glob = any(char in clean_query for char in ["*", "?", "[", "]"])
        pattern = clean_query.lower()

        matches: List[SearchMatch] = []
        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
            for f in files:
                if extension and not f.endswith(extension):
                    continue

                # Exclude sensitive files
                f_lower_check = f.lower()
                if f_lower_check.startswith(".env") or f_lower_check.endswith((".key", ".pem", ".p12", ".pfx")):
                    continue

                full_path = Path(root) / f
                rel_path = os.path.relpath(full_path, str(self.workspace_root)).replace("\\", "/")
                rel_lower = rel_path.lower()
                f_lower = f.lower()

                matched = False
                score = 0.5
                if is_glob:
                    if fnmatch.fnmatch(rel_lower, pattern) or fnmatch.fnmatch(f_lower, pattern):
                        matched = True
                        score = 0.9
                else:
                    if pattern in rel_lower or pattern in f_lower:
                        matched = True
                        score = 1.0 if pattern == f_lower else 0.7

                if matched:
                    matches.append(
                        SearchMatch(
                            tier="path",
                            file=rel_path,
                            line=1,
                            column=1,
                            text=rel_path,
                            score=score,
                        )
                    )
                    if len(matches) >= max_results:
                        return matches

        return sorted(matches, key=lambda m: m.score, reverse=True)
