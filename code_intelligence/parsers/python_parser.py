import ast
import hashlib
import sys
from typing import Any, List, Optional, Set
from code_intelligence.models import (
    ParsedCall,
    ParsedFile,
    ParsedImport,
    ParsedSymbol,
    SymbolKindEnum,
)
from code_intelligence.parsers.base import BaseParser

# Standard library module names in Python 3.10+
_STDLIB_MODULES: Set[str] = set(sys.stdlib_module_names) if hasattr(sys, "stdlib_module_names") else {
    "os", "sys", "re", "json", "math", "time", "datetime", "typing", "collections", "pathlib",
    "dataclasses", "abc", "uuid", "enum", "subprocess", "logging", "asyncio", "unittest",
    "contextlib", "functools", "itertools", "io", "shutil", "tempfile", "traceback", "hashlib"
}


class PythonASTParser(BaseParser):
    """Deterministic AST-based symbol and import parser for Python source files."""

    @property
    def language(self) -> str:
        return "python"

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

        try:
            tree = ast.parse(code, filename=filepath)
        except SyntaxError as e:
            parsed_file.errors.append(f"SyntaxError: {str(e)} (line {e.lineno})")
            return parsed_file
        except Exception as e:
            parsed_file.errors.append(f"AST Parsing Error: {str(e)}")
            return parsed_file

        self._extract_imports(tree, parsed_file)
        self._extract_symbols(tree, parsed_file)

        return parsed_file

    def _extract_imports(self, tree: ast.AST, parsed_file: ParsedFile) -> None:
        """Extracts all top-level and nested import statements."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_pkg = alias.name.split(".")[0]
                    is_ext = top_pkg in _STDLIB_MODULES or not (alias.name.startswith(".") or alias.name.startswith("code_intelligence") or alias.name.startswith("apps"))
                    parsed_file.imports.append(
                        ParsedImport(
                            module=alias.name,
                            symbol_name=None,
                            alias=alias.asname,
                            is_external=is_ext,
                            line_number=node.lineno,
                        )
                    )
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                top_pkg = (node.module or "").split(".")[0]
                is_ext = (node.level == 0) and (top_pkg in _STDLIB_MODULES)
                for alias in node.names:
                    parsed_file.imports.append(
                        ParsedImport(
                            module=module,
                            symbol_name=alias.name,
                            alias=alias.asname,
                            is_external=is_ext,
                            line_number=node.lineno,
                        )
                    )

    def _extract_symbols(self, tree: ast.AST, parsed_file: ParsedFile) -> None:
        """Extracts functions, async functions, classes, methods, docstrings, and signatures."""
        for node in tree.body:
            self._visit_node(node, parent_qualname="", parent_name=None, parsed_file=parsed_file)

    def _visit_node(
        self,
        node: ast.AST,
        parent_qualname: str,
        parent_name: Optional[str],
        parsed_file: ParsedFile,
    ) -> None:
        if isinstance(node, ast.ClassDef):
            qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
            extends = [self._get_expr_name(base) for base in node.bases]
            docstring = ast.get_docstring(node)

            class_symbol = ParsedSymbol(
                name=node.name,
                qualified_name=qualname,
                kind=SymbolKindEnum.CLASS,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                signature=f"class {node.name}({', '.join(extends)})" if extends else f"class {node.name}",
                docstring=docstring,
                parent_name=parent_name,
                extends=[e for e in extends if e],
            )
            parsed_file.symbols.append(class_symbol)

            # Visit class body members (methods, nested classes)
            for child in node.body:
                self._visit_node(
                    child,
                    parent_qualname=qualname,
                    parent_name=node.name,
                    parsed_file=parsed_file,
                )

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_async = isinstance(node, ast.AsyncFunctionDef)
            is_method = parent_name is not None
            kind = SymbolKindEnum.METHOD if is_method else (SymbolKindEnum.ASYNC_FUNCTION if is_async else SymbolKindEnum.FUNCTION)
            qualname = f"{parent_qualname}.{node.name}" if parent_qualname else node.name
            docstring = ast.get_docstring(node)
            sig = self._format_signature(node, is_async=is_async)
            decorators = [self._get_expr_name(d) for d in getattr(node, "decorator_list", [])]

            # Collect calls inside this function body
            calls = self._collect_calls(node)

            func_symbol = ParsedSymbol(
                name=node.name,
                qualified_name=qualname,
                kind=kind,
                start_line=node.lineno,
                end_line=getattr(node, "end_lineno", node.lineno),
                signature=sig,
                docstring=docstring,
                parent_name=parent_name,
                calls=calls,
                metadata={"decorators": decorators} if decorators else {},
            )
            parsed_file.symbols.append(func_symbol)

            # Visit nested functions/classes inside function body
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    self._visit_node(
                        child,
                        parent_qualname=qualname,
                        parent_name=node.name,
                        parsed_file=parsed_file,
                    )

    def _format_signature(self, node: Any, is_async: bool = False) -> str:
        """Constructs human-readable function/method signature."""
        prefix = "async def " if is_async else "def "
        params: List[str] = []

        args = node.args
        for arg in args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            params.append(arg_str)

        if args.vararg:
            var_str = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                var_str += f": {ast.unparse(args.vararg.annotation)}"
            params.append(var_str)

        for arg in args.kwonlyargs:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            params.append(arg_str)

        if args.kwarg:
            kw_str = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kw_str += f": {ast.unparse(args.kwarg.annotation)}"
            params.append(kw_str)

        sig = f"{prefix}{node.name}({', '.join(params)})"
        if getattr(node, "returns", None):
            sig += f" -> {ast.unparse(node.returns)}"
        return sig

    def _collect_calls(self, node: ast.AST) -> List[ParsedCall]:
        """Extracts names, line numbers, and expressions of called functions or methods inside a node."""
        calls: List[ParsedCall] = []
        seen = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = self._get_expr_name(child.func)
                line_no = getattr(child, "lineno", getattr(node, "lineno", 1))
                if name and name not in {"print", "len", "range", "isinstance", "getattr", "setattr"}:
                    key = (name, line_no)
                    if key not in seen:
                        seen.add(key)
                        calls.append(ParsedCall(name=name, line_number=line_no, callee_expr=name))
        return calls

    def _get_expr_name(self, expr: ast.AST) -> str:
        """Converts an AST expression to a qualified string name (e.g. self.helper, os.path.join)."""
        if isinstance(expr, ast.Name):
            return expr.id
        elif isinstance(expr, ast.Attribute):
            base_name = self._get_expr_name(expr.value)
            return f"{base_name}.{expr.attr}" if base_name else expr.attr
        return ""
