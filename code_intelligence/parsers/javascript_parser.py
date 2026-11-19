import hashlib
import re
from typing import List, Optional, Tuple
from code_intelligence.models import (
    ParsedFile,
    ParsedImport,
    ParsedSymbol,
    SymbolKindEnum,
)
from code_intelligence.parsers.base import BaseParser


class JavaScriptParser(BaseParser):
    """Deterministic symbol and import extractor for JavaScript/JSX files."""

    @property
    def language(self) -> str:
        return "javascript"

    # Regex patterns for imports
    RE_ES6_IMPORT = re.compile(r'import\s+(?:([\w\*\s{},]+)\s+from\s+)?[\'"]([^\'"]+)[\'"]', re.MULTILINE)
    RE_REQUIRE = re.compile(r'(?:const|let|var)\s+([\w\s{},]+)\s*=\s*require\([\'"]([^\'"]+)[\'"]\)', re.MULTILINE)

    # Regex patterns for symbols
    RE_CLASS = re.compile(r'^(?:export\s+(?:default\s+)?)?class\s+([A-Za-z0-9_$]+)(?:\s+extends\s+([A-Za-z0-9_$.]+))?', re.MULTILINE)
    RE_FUNCTION = re.compile(r'^(?:export\s+(?:default\s+)?)?(async\s+)?function\s*([A-Za-z0-9_$]+)\s*\(([^)]*)\)', re.MULTILINE)
    RE_ARROW = re.compile(r'^(?:export\s+)?(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=\s*(async\s+)?(?:\(([^)]*)\)|([A-Za-z0-9_$]+))\s*=>', re.MULTILINE)
    RE_METHOD = re.compile(r'^\s*(async\s+)?([A-Za-z0-9_$]+)\s*\(([^)]*)\)(?::\s*[^{]+)?\s*\{', re.MULTILINE)

    def parse_source(self, code: str, filepath: str = "") -> ParsedFile:
        code_bytes = code.encode("utf-8")
        file_hash = hashlib.sha256(code_bytes).hexdigest()
        size_bytes = len(code_bytes)
        lines = code.splitlines()
        line_count = len(lines)

        parsed_file = ParsedFile(
            path=filepath,
            language=self.language,
            hash=file_hash,
            size_bytes=size_bytes,
            line_count=line_count,
        )

        self._extract_imports(code, lines, parsed_file)
        self._extract_symbols(code, lines, parsed_file)

        return parsed_file

    def _extract_imports(self, code: str, lines: List[str], parsed_file: ParsedFile) -> None:
        # ES6 imports
        for match in self.RE_ES6_IMPORT.finditer(code):
            raw_symbols = match.group(1) or ""
            module_path = match.group(2)
            line_num = code[: match.start()].count("\n") + 1
            is_ext = not (module_path.startswith(".") or module_path.startswith("/"))

            if "{" in raw_symbols and "}" in raw_symbols:
                inner = raw_symbols[raw_symbols.find("{") + 1 : raw_symbols.find("}")]
                for sym in inner.split(","):
                    sym = sym.strip()
                    if sym:
                        parts = sym.split(" as ")
                        name = parts[0].strip()
                        alias = parts[1].strip() if len(parts) > 1 else None
                        parsed_file.imports.append(
                            ParsedImport(
                                module=module_path,
                                symbol_name=name,
                                alias=alias,
                                is_external=is_ext,
                                line_number=line_num,
                            )
                        )
            else:
                default_name = raw_symbols.strip() or None
                parsed_file.imports.append(
                    ParsedImport(
                        module=module_path,
                        symbol_name=default_name,
                        is_external=is_ext,
                        line_number=line_num,
                    )
                )

        # CommonJS require()
        for match in self.RE_REQUIRE.finditer(code):
            raw_var = match.group(1).strip()
            module_path = match.group(2)
            line_num = code[: match.start()].count("\n") + 1
            is_ext = not (module_path.startswith(".") or module_path.startswith("/"))
            parsed_file.imports.append(
                ParsedImport(
                    module=module_path,
                    symbol_name=raw_var,
                    is_external=is_ext,
                    line_number=line_num,
                )
            )

    def _extract_symbols(self, code: str, lines: List[str], parsed_file: ParsedFile) -> None:
        # Classes
        for match in self.RE_CLASS.finditer(code):
            class_name = match.group(1)
            extends_class = match.group(2)
            line_start = code[: match.start()].count("\n") + 1
            line_end = self._find_closing_brace_line(code, match.start(), lines)

            extends_list = [extends_class] if extends_class else []
            sig = f"class {class_name}" + (f" extends {extends_class}" if extends_class else "")

            parsed_file.symbols.append(
                ParsedSymbol(
                    name=class_name,
                    qualified_name=class_name,
                    kind=SymbolKindEnum.CLASS,
                    start_line=line_start,
                    end_line=line_end,
                    signature=sig,
                    extends=extends_list,
                )
            )

            # Extract methods inside this class block
            class_block = code[match.start() : self._find_closing_brace_pos(code, match.start())]
            for m_match in self.RE_METHOD.finditer(class_block):
                is_async = bool(m_match.group(1))
                m_name = m_match.group(2)
                if m_name in {"if", "for", "while", "switch", "catch"}:
                    continue
                params = m_match.group(3).strip()
                m_line = line_start + class_block[: m_match.start()].count("\n")
                m_end = self._find_closing_brace_line(code, match.start() + m_match.start(), lines)
                qualname = f"{class_name}.{m_name}"
                sig_m = f"{'async ' if is_async else ''}{m_name}({params})"

                parsed_file.symbols.append(
                    ParsedSymbol(
                        name=m_name,
                        qualified_name=qualname,
                        kind=SymbolKindEnum.METHOD,
                        start_line=m_line,
                        end_line=m_end,
                        signature=sig_m,
                        parent_name=class_name,
                    )
                )

        # Standalone Functions
        for match in self.RE_FUNCTION.finditer(code):
            is_async = bool(match.group(1))
            fn_name = match.group(2)
            params = match.group(3).strip()
            line_start = code[: match.start()].count("\n") + 1
            line_end = self._find_closing_brace_line(code, match.start(), lines)
            sig = f"{'async ' if is_async else ''}function {fn_name}({params})"

            parsed_file.symbols.append(
                ParsedSymbol(
                    name=fn_name,
                    qualified_name=fn_name,
                    kind=SymbolKindEnum.ASYNC_FUNCTION if is_async else SymbolKindEnum.FUNCTION,
                    start_line=line_start,
                    end_line=line_end,
                    signature=sig,
                )
            )

        # Arrow Functions / Functional Components
        for match in self.RE_ARROW.finditer(code):
            fn_name = match.group(1)
            is_async = bool(match.group(2))
            params = (match.group(3) or match.group(4) or "").strip()
            line_start = code[: match.start()].count("\n") + 1
            line_end = self._find_closing_brace_line(code, match.start(), lines)
            sig = f"const {fn_name} = {'async ' if is_async else ''}({params}) =>"

            parsed_file.symbols.append(
                ParsedSymbol(
                    name=fn_name,
                    qualified_name=fn_name,
                    kind=SymbolKindEnum.ASYNC_FUNCTION if is_async else SymbolKindEnum.FUNCTION,
                    start_line=line_start,
                    end_line=line_end,
                    signature=sig,
                )
            )

    def _find_closing_brace_pos(self, text: str, start_index: int) -> int:
        open_pos = text.find("{", start_index)
        if open_pos == -1:
            return len(text)
        depth = 1
        pos = open_pos + 1
        while pos < len(text) and depth > 0:
            ch = text[pos]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            pos += 1
        return pos

    def _find_closing_brace_line(self, text: str, start_index: int, lines: List[str]) -> int:
        end_pos = self._find_closing_brace_pos(text, start_index)
        line_num = text[:end_pos].count("\n") + 1
        return min(line_num, len(lines))
