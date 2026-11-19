from pathlib import Path
from typing import Dict, Optional
from code_intelligence.parsers.base import BaseParser
from code_intelligence.parsers.javascript_parser import JavaScriptParser
from code_intelligence.parsers.python_parser import PythonASTParser
from code_intelligence.parsers.typescript_parser import TypeScriptParser


class ParserRegistry:
    """Registry mapping file extensions to language-specific AST/code parsers."""

    def __init__(self) -> None:
        self._parsers: Dict[str, BaseParser] = {}
        self._extension_map: Dict[str, str] = {}

        # Register default parsers
        self.register_parser(PythonASTParser(), [".py"])
        self.register_parser(JavaScriptParser(), [".js", ".jsx", ".mjs", ".cjs"])
        self.register_parser(TypeScriptParser(), [".ts", ".tsx", ".mts", ".cts"])

    def register_parser(self, parser: BaseParser, extensions: list[str]) -> None:
        self._parsers[parser.language] = parser
        for ext in extensions:
            self._extension_map[ext.lower()] = parser.language

    def get_parser_for_path(self, path: Path | str) -> Optional[BaseParser]:
        ext = Path(path).suffix.lower()
        lang = self._extension_map.get(ext)
        if lang:
            return self._parsers.get(lang)
        return None

    def get_parser_for_language(self, language: str) -> Optional[BaseParser]:
        return self._parsers.get(language.lower())

    def supported_extensions(self) -> list[str]:
        return list(self._extension_map.keys())


# Singleton instance
default_parser_registry = ParserRegistry()
