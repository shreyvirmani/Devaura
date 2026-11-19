import hashlib
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from code_intelligence.models import ParsedFile
from code_intelligence.parsers.registry import default_parser_registry

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


class FileIndexer:
    """Scans and parses source files within a repository workspace."""

    def __init__(self, workspace_root: Path | str = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.registry = default_parser_registry

    def scan_workspace(self, path_filter: Optional[str] = None) -> List[Path]:
        """Discovers all supported source files respecting ignore directories."""
        base_dir = self.workspace_root
        if path_filter:
            target = (self.workspace_root / path_filter).resolve()
            if target.exists() and str(target).startswith(str(self.workspace_root)):
                base_dir = target

        matched_files: List[Path] = []
        supported_exts = set(self.registry.supported_extensions())

        if base_dir.is_file():
            if base_dir.suffix.lower() in supported_exts:
                return [base_dir]
            return []

        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in _DEFAULT_IGNORED_DIRS]
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() in supported_exts:
                    matched_files.append(p)

        return sorted(matched_files)

    def parse_files(self, file_paths: List[Path]) -> List[ParsedFile]:
        """Parses discovered file paths using registered AST parsers."""
        parsed_files: List[ParsedFile] = []
        for p in file_paths:
            parser = self.registry.get_parser_for_path(p)
            if parser:
                pf = parser.parse_file(p, workspace_root=self.workspace_root)
                parsed_files.append(pf)
        return parsed_files

    def index_workspace(self, path_filter: Optional[str] = None) -> List[ParsedFile]:
        """Convenience method combining discovery and parsing."""
        files = self.scan_workspace(path_filter)
        return self.parse_files(files)
