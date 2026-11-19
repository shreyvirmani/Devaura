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
    ".idea",
    ".vscode",
}

_SENSITIVE_FILE_PATTERNS: Set[str] = {
    ".env",
    "id_rsa",
    "id_ed25519",
}

_SENSITIVE_EXTENSIONS: Set[str] = {
    ".pem",
    ".key",
    ".pkcs12",
    ".pfx",
    ".p12",
}

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB limit


class FileIndexer:
    """Scans and parses source files within a repository workspace with security and resource boundaries."""

    def __init__(
        self,
        workspace_root: Path | str = ".",
        max_files: int = 2000,
        max_file_size_bytes: int = MAX_FILE_SIZE_BYTES,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.registry = default_parser_registry
        self.max_files = max_files
        self.max_file_size_bytes = max_file_size_bytes

    def is_sensitive(self, file_path: Path) -> bool:
        """Determines if a file matches sensitive credential or private key patterns."""
        name = file_path.name.lower()
        if name in _SENSITIVE_FILE_PATTERNS or name.startswith(".env"):
            return True
        if file_path.suffix.lower() in _SENSITIVE_EXTENSIONS:
            return True
        return False

    def scan_workspace(self, path_filter: Optional[str] = None) -> List[Path]:
        """Discovers all supported source files respecting ignore directories and security limits."""
        base_dir = self.workspace_root
        if path_filter:
            target = (self.workspace_root / path_filter).resolve()
            if target.exists() and str(target).startswith(str(self.workspace_root)):
                base_dir = target

        matched_files: List[Path] = []
        supported_exts = set(self.registry.supported_extensions())

        if base_dir.is_file():
            if not self.is_sensitive(base_dir) and base_dir.suffix.lower() in supported_exts:
                if base_dir.stat().st_size <= self.max_file_size_bytes:
                    return [base_dir]
            return []

        for root, dirs, files in os.walk(base_dir):
            dirs[:] = [d for d in dirs if d not in _DEFAULT_IGNORED_DIRS]
            for file in files:
                p = Path(root) / file
                if self.is_sensitive(p):
                    continue
                if p.suffix.lower() in supported_exts:
                    try:
                        if p.stat().st_size <= self.max_file_size_bytes:
                            matched_files.append(p)
                    except OSError:
                        continue
                if len(matched_files) >= self.max_files:
                    break
            if len(matched_files) >= self.max_files:
                break

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
