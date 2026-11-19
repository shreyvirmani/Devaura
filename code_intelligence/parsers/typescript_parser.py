import re
from typing import List
from code_intelligence.models import (
    ParsedFile,
    ParsedSymbol,
    SymbolKindEnum,
)
from code_intelligence.parsers.javascript_parser import JavaScriptParser


class TypeScriptParser(JavaScriptParser):
    """Deterministic symbol and import extractor for TypeScript/TSX files."""

    @property
    def language(self) -> str:
        return "typescript"

    RE_INTERFACE = re.compile(
        r'^(?:export\s+)?interface\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$,\s]+))?',
        re.MULTILINE,
    )
    RE_TYPE_ALIAS = re.compile(
        r'^(?:export\s+)?type\s+([A-Za-z0-9_$]+)(?:<[^>]+>)?\s*=',
        re.MULTILINE,
    )

    def _extract_symbols(self, code: str, lines: List[str], parsed_file: ParsedFile) -> None:
        # Run base JS symbol extraction (classes, methods, functions, arrow functions)
        super()._extract_symbols(code, lines, parsed_file)

        # Extract TypeScript interfaces
        for match in self.RE_INTERFACE.finditer(code):
            name = match.group(1)
            raw_extends = match.group(2)
            extends_list = [e.strip() for e in raw_extends.split(",") if e.strip()] if raw_extends else []
            line_start = code[: match.start()].count("\n") + 1
            line_end = self._find_closing_brace_line(code, match.start(), lines)
            sig = f"interface {name}" + (f" extends {raw_extends.strip()}" if raw_extends else "")

            parsed_file.symbols.append(
                ParsedSymbol(
                    name=name,
                    qualified_name=name,
                    kind=SymbolKindEnum.INTERFACE,
                    start_line=line_start,
                    end_line=line_end,
                    signature=sig,
                    extends=extends_list,
                )
            )

        # Extract TypeScript type aliases
        for match in self.RE_TYPE_ALIAS.finditer(code):
            name = match.group(1)
            line_start = code[: match.start()].count("\n") + 1
            semicolon_pos = code.find(";", match.end())
            line_end = code[:semicolon_pos].count("\n") + 1 if semicolon_pos != -1 else line_start

            parsed_file.symbols.append(
                ParsedSymbol(
                    name=name,
                    qualified_name=name,
                    kind=SymbolKindEnum.TYPE_ALIAS,
                    start_line=line_start,
                    end_line=line_end,
                    signature=f"type {name}",
                )
            )
