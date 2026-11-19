from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from code_intelligence.models import ParsedFile


class BaseParser(ABC):
    """Abstract base parser interface for AST-based code extraction."""

    @property
    @abstractmethod
    def language(self) -> str:
        """The language supported by this parser (e.g., 'python', 'javascript', 'typescript')."""
        pass

    @abstractmethod
    def parse_source(self, code: str, filepath: str = "") -> ParsedFile:
        """Parses source code into a structured ParsedFile containing symbols, imports, and metrics."""
        pass

    def parse_file(self, path: Path, workspace_root: Optional[Path] = None) -> ParsedFile:
        """Reads file from disk and parses it."""
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            rel_path = str(path.relative_to(workspace_root)) if workspace_root else str(path)
            return ParsedFile(
                path=rel_path,
                language=self.language,
                hash="",
                size_bytes=0,
                line_count=0,
                errors=[f"Failed to read file: {str(e)}"],
            )

        rel_path = str(path.relative_to(workspace_root)) if workspace_root else str(path)
        # Normalize forward slashes for cross-platform consistency
        rel_path = rel_path.replace("\\", "/")
        return self.parse_source(content, filepath=rel_path)
