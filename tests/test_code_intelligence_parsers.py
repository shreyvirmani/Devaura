from pathlib import Path
import pytest
from code_intelligence.models import SymbolKindEnum
from code_intelligence.parsers.javascript_parser import JavaScriptParser
from code_intelligence.parsers.python_parser import PythonASTParser
from code_intelligence.parsers.registry import ParserRegistry, default_parser_registry
from code_intelligence.parsers.typescript_parser import TypeScriptParser

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "fixture_repo"


def test_python_ast_parser_core():
    parser = PythonASTParser()
    core_file = FIXTURE_PATH / "calculator" / "core.py"
    parsed = parser.parse_file(core_file, workspace_root=FIXTURE_PATH)

    assert parsed.language == "python"
    assert parsed.line_count > 20
    assert len(parsed.errors) == 0
    assert len(parsed.hash) == 64

    # Check symbols
    symbol_names = [s.name for s in parsed.symbols]
    assert "Calculator" in symbol_names
    assert "add" in symbol_names
    assert "divide" in symbol_names
    assert "_validate_number" in symbol_names

    # Check method signatures and hierarchy
    add_sym = next(s for s in parsed.symbols if s.name == "add")
    assert add_sym.kind == SymbolKindEnum.METHOD
    assert add_sym.parent_name == "Calculator"
    assert add_sym.qualified_name == "Calculator.add"
    assert "def add(self, a" in add_sym.signature
    assert "Adds two numbers." in (add_sym.docstring or "")
    assert "_validate_number" in add_sym.calls or "format_result" in add_sym.calls

    # Check imports
    imported_modules = [i.module for i in parsed.imports]
    assert any("calculator.utils" in m for m in imported_modules)


def test_python_ast_parser_inheritance():
    parser = PythonASTParser()
    adv_file = FIXTURE_PATH / "calculator" / "advanced.py"
    parsed = parser.parse_file(adv_file, workspace_root=FIXTURE_PATH)

    sci_class = next(s for s in parsed.symbols if s.name == "ScientificCalculator")
    assert sci_class.kind == SymbolKindEnum.CLASS
    assert "Calculator" in sci_class.extends


def test_python_ast_parser_syntax_error():
    parser = PythonASTParser()
    broken_code = "def invalid_syntax(a, b\n    return a +"
    parsed = parser.parse_source(broken_code, filepath="broken.py")
    assert len(parsed.errors) > 0
    assert "SyntaxError" in parsed.errors[0]


def test_javascript_parser():
    parser = JavaScriptParser()
    code = """
import { useState, useEffect } from 'react';
import axios from 'axios';

export class DataFetcher extends BaseService {
    async fetchData(url) {
        return axios.get(url);
    }
}

export function helperUtil(x, y) {
    return x + y;
}

const arrowHandler = async (evt) => {
    console.log(evt);
};
"""
    parsed = parser.parse_source(code, filepath="test.js")
    assert parsed.language == "javascript"
    sym_names = [s.name for s in parsed.symbols]
    assert "DataFetcher" in sym_names
    assert "fetchData" in sym_names
    assert "helperUtil" in sym_names
    assert "arrowHandler" in sym_names

    fetch_method = next(s for s in parsed.symbols if s.name == "fetchData")
    assert fetch_method.kind == SymbolKindEnum.METHOD
    assert fetch_method.parent_name == "DataFetcher"

    import_modules = [i.module for i in parsed.imports]
    assert "react" in import_modules
    assert "axios" in import_modules


def test_typescript_parser():
    parser = TypeScriptParser()
    code = """
export interface UserProfile extends BaseEntity {
    id: string;
    username: string;
    isActive: boolean;
}

export type ID = string | number;

export class UserManager {
    getUser(id: ID): UserProfile {
        return { id: String(id), username: "alice", isActive: true };
    }
}
"""
    parsed = parser.parse_source(code, filepath="types.ts")
    assert parsed.language == "typescript"
    sym_names = [s.name for s in parsed.symbols]
    assert "UserProfile" in sym_names
    assert "ID" in sym_names
    assert "UserManager" in sym_names
    assert "getUser" in sym_names

    iface = next(s for s in parsed.symbols if s.name == "UserProfile")
    assert iface.kind == SymbolKindEnum.INTERFACE
    assert "BaseEntity" in iface.extends


def test_parser_registry():
    registry = ParserRegistry()
    py_parser = registry.get_parser_for_path("foo/bar.py")
    assert py_parser is not None
    assert py_parser.language == "python"

    ts_parser = registry.get_parser_for_path("src/components/Button.tsx")
    assert ts_parser is not None
    assert ts_parser.language == "typescript"

    js_parser = registry.get_parser_for_path("index.mjs")
    assert js_parser is not None
    assert js_parser.language == "javascript"

    unsupported = registry.get_parser_for_path("data.csv")
    assert unsupported is None
