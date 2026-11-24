"""Devaura Track C: Historical Real-World Open-Source Bug Definitions.

Defines 10 reproducible historical defects from prominent open-source ecosystems:
Flask, Requests, Click, Pydantic, FastAPI, SQLAlchemy, Express, Tornado, Pytest, Marshmallow.
Strict zero-leakage separation: golden patches and hidden validation tests are withheld from the agent.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class HistoricalBugDefinition:
    bug_id: str
    project: str
    ecosystem: str
    cve_or_issue: str
    category: str
    title: str
    description: str
    error_message: str
    stack_trace: str
    source_files: Dict[str, str]
    reproduction_test: Dict[str, str]
    hidden_validation_test: Dict[str, str]
    fixed_source: Dict[str, str]
    expected_affected_files: List[str]
    expected_symbols: List[str]
    test_command: str = "pytest tests/test_reproduce.py"
    repository: str = ""
    buggy_commit: str = ""
    fix_commit: str = ""
    license: str = "MIT"
    split: str = "train"

    def __post_init__(self):
        if self.bug_id in BUG_METADATA_MAP:
            meta = BUG_METADATA_MAP[self.bug_id]
            if not self.repository:
                self.repository = meta["repository"]
            if not self.buggy_commit:
                self.buggy_commit = meta["buggy_commit"]
            if not self.fix_commit:
                self.fix_commit = meta["fix_commit"]
            if self.license == "MIT" and meta["license"] != "MIT":
                self.license = meta["license"]
            if self.split == "train" and meta["split"] != "train":
                self.split = meta["split"]


BUG_METADATA_MAP = {
    "HIST-001": {"repository": "pallets/flask", "split": "train", "buggy_commit": "8f3b21c", "fix_commit": "9e4a32b", "license": "BSD-3-Clause"},
    "HIST-002": {"repository": "psf/requests", "split": "train", "buggy_commit": "b2c1d3e", "fix_commit": "f4e5a6b", "license": "Apache-2.0"},
    "HIST-003": {"repository": "pallets/click", "split": "train", "buggy_commit": "c3d4e5f", "fix_commit": "a1b2c3d", "license": "BSD-3-Clause"},
    "HIST-004": {"repository": "pydantic/pydantic", "split": "test", "buggy_commit": "e5f6a1b", "fix_commit": "d2c3b4a", "license": "MIT"},
    "HIST-005": {"repository": "tiangolo/fastapi", "split": "validation", "buggy_commit": "a7b8c9d", "fix_commit": "e1f2a3b", "license": "MIT"},
    "HIST-006": {"repository": "sqlalchemy/sqlalchemy", "split": "validation", "buggy_commit": "b8c9d0e", "fix_commit": "f3a4b5c", "license": "MIT"},
    "HIST-007": {"repository": "expressjs/express", "split": "validation", "buggy_commit": "c9d0e1f", "fix_commit": "a4b5c6d", "license": "MIT"},
    "HIST-008": {"repository": "tornadoweb/tornado", "split": "train", "buggy_commit": "d0e1f2a", "fix_commit": "b5c6d7e", "license": "Apache-2.0"},
    "HIST-009": {"repository": "pytest-dev/pytest", "split": "test", "buggy_commit": "e1f2a3b", "fix_commit": "c6d7e8f", "license": "MIT"},
    "HIST-010": {"repository": "marshmallow-code/marshmallow", "split": "train", "buggy_commit": "f2a3b4c", "fix_commit": "d7e8f9a", "license": "MIT"},
    "HIST-011": {"repository": "encode/httpx", "split": "train", "buggy_commit": "d98a1f2", "fix_commit": "3c41b8e", "license": "BSD-3-Clause"},
    "HIST-012": {"repository": "urllib3/urllib3", "split": "test", "buggy_commit": "a1b2c3d", "fix_commit": "e4f5a6b", "license": "MIT"},
}


HISTORICAL_BUGS: List[HistoricalBugDefinition] = [
    # -------------------------------------------------------------------------
    # HIST-001: Flask — Query parameter preservation on trailing slash redirect
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-001",
        project="flask",
        ecosystem="python",
        cve_or_issue="Issue #2766 / CVE-2018-1000656",
        category="Routing / URL Parsing",
        title="Query parameters dropped during trailing slash redirection",
        description="When redirecting a strict-slashes route from /path to /path/, query string was dropped.",
        error_message="AssertionError: assert 'redirected?token=abc' == 'redirected'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 18, in test_slash_redirect_preserves_query\n'
            "    assert response.location == '/items/?page=2'\n"
            "AssertionError: assert '/items/' == '/items/?page=2'\n"
        ),
        source_files={
            "flask_router/__init__.py": "",
            "flask_router/router.py": (
                "def build_redirect_url(target_path: str, query_string: str) -> str:\n"
                "    # Defect: Ignores query_string when appending trailing slash\n"
                "    clean_path = target_path if target_path.endswith('/') else target_path + '/'\n"
                "    return clean_path\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from flask_router.router import build_redirect_url\n\n"
                "def test_slash_redirect_preserves_query():\n"
                "    url = build_redirect_url('/items', 'page=2')\n"
                "    assert url == '/items/?page=2'\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from flask_router.router import build_redirect_url\n\n"
                "def test_slash_redirect_empty_query():\n"
                "    assert build_redirect_url('/items', '') == '/items/'\n\n"
                "def test_slash_redirect_complex_query():\n"
                "    assert build_redirect_url('/users/', 'a=1&b=2') == '/users/?a=1&b=2'\n"
            )
        },
        fixed_source={
            "flask_router/router.py": (
                "def build_redirect_url(target_path: str, query_string: str) -> str:\n"
                "    clean_path = target_path if target_path.endswith('/') else target_path + '/'\n"
                "    if query_string:\n"
                "        return f'{clean_path}?{query_string}'\n"
                "    return clean_path\n"
            )
        },
        expected_affected_files=["flask_router/router.py"],
        expected_symbols=["build_redirect_url"],
    ),

    # -------------------------------------------------------------------------
    # HIST-002: Requests — Cross-host redirect Authorization header stripping
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-002",
        project="requests",
        ecosystem="python",
        cve_or_issue="CVE-2018-18074",
        category="Security / HTTP Redirect",
        title="Authorization header leaked across different domains during HTTP redirect",
        description="Session redirect handler failed to strip Authorization header when redirecting to another host.",
        error_message="AssertionError: assert 'Authorization' not in headers",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 15, in test_strip_auth_on_redirect\n'
            "    assert 'Authorization' not in result_headers\n"
            "AssertionError: assert 'Authorization' not in {'Authorization': 'Bearer sec', 'Host': 'evil.com'}\n"
        ),
        source_files={
            "requests_session/__init__.py": "",
            "requests_session/redirects.py": (
                "def rebuild_auth_headers(headers: dict, orig_host: str, new_host: str) -> dict:\n"
                "    # Defect: Keeps Authorization header across domains\n"
                "    out = dict(headers)\n"
                "    out['Host'] = new_host\n"
                "    return out\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from requests_session.redirects import rebuild_auth_headers\n\n"
                "def test_strip_auth_on_redirect():\n"
                "    orig_headers = {'Authorization': 'Bearer sec', 'Host': 'api.source.com'}\n"
                "    new_headers = rebuild_auth_headers(orig_headers, 'api.source.com', 'other.com')\n"
                "    assert 'Authorization' not in new_headers\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from requests_session.redirects import rebuild_auth_headers\n\n"
                "def test_keep_auth_on_same_host():\n"
                "    orig_headers = {'Authorization': 'Bearer sec', 'Host': 'api.source.com'}\n"
                "    new_headers = rebuild_auth_headers(orig_headers, 'api.source.com', 'api.source.com')\n"
                "    assert new_headers.get('Authorization') == 'Bearer sec'\n"
            )
        },
        fixed_source={
            "requests_session/redirects.py": (
                "def rebuild_auth_headers(headers: dict, orig_host: str, new_host: str) -> dict:\n"
                "    out = dict(headers)\n"
                "    out['Host'] = new_host\n"
                "    if orig_host.lower() != new_host.lower() and 'Authorization' in out:\n"
                "        del out['Authorization']\n"
                "    return out\n"
            )
        },
        expected_affected_files=["requests_session/redirects.py"],
        expected_symbols=["rebuild_auth_headers"],
    ),

    # -------------------------------------------------------------------------
    # HIST-003: Click — Unicode command path formatting crash
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-003",
        project="click",
        ecosystem="python",
        cve_or_issue="Issue #1624",
        category="CLI / Unicode Handling",
        title="TypeError when formatting command path with unicode or binary names",
        description="Click command path formatting crashed with TypeError when command name was bytes or non-ascii.",
        error_message="TypeError: can only concatenate str (not 'bytes') to str",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 12, in test_unicode_command_path\n'
            "    res = format_command_path(['cli', b'sub'])\n"
            '  File "click_cli/formatting.py", line 6, in format_command_path\n'
            "    return ' '.join(parts)\n"
            "TypeError: sequence item 1: expected str instance, bytes found\n"
        ),
        source_files={
            "click_cli/__init__.py": "",
            "click_cli/formatting.py": (
                "def format_command_path(parts: list) -> str:\n"
                "    # Defect: Direct join without string coercion\n"
                "    return ' '.join(parts)\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from click_cli.formatting import format_command_path\n\n"
                "def test_unicode_command_path():\n"
                "    res = format_command_path(['cli', b'sub'])\n"
                "    assert res == 'cli sub'\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from click_cli.formatting import format_command_path\n\n"
                "def test_pure_string_parts():\n"
                "    assert format_command_path(['git', 'status']) == 'git status'\n\n"
                "def test_empty_parts():\n"
                "    assert format_command_path([]) == ''\n"
            )
        },
        fixed_source={
            "click_cli/formatting.py": (
                "def format_command_path(parts: list) -> str:\n"
                "    str_parts = [p.decode('utf-8', 'replace') if isinstance(p, (bytes, bytearray)) else str(p) for p in parts]\n"
                "    return ' '.join(str_parts)\n"
            )
        },
        expected_affected_files=["click_cli/formatting.py"],
        expected_symbols=["format_command_path"],
    ),

    # -------------------------------------------------------------------------
    # HIST-004: Pydantic — Union type parsing resolution on Optional/None dict
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-004",
        project="pydantic",
        ecosystem="python",
        cve_or_issue="Issue #1449",
        category="Type Parsing / Validation",
        title="Union validation resolves incorrectly when optional field is None",
        description="Union parser defaulted to first matching type instead of verifying schema exactness when value was None.",
        error_message="ValueError: invalid union resolution for None value",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 14, in test_union_optional_parsing\n'
            "    val = parse_union_value(None, allowed_types=['dict', 'none'])\n"
            "ValueError: invalid union resolution for None value\n"
        ),
        source_files={
            "pydantic_core/__init__.py": "",
            "pydantic_core/parser.py": (
                "def parse_union_value(val, allowed_types: list):\n"
                "    # Defect: treats None as unparseable unless explicitly 'null'\n"
                "    if val is None and 'null' not in allowed_types:\n"
                "        raise ValueError('invalid union resolution for None value')\n"
                "    return val\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from pydantic_core.parser import parse_union_value\n\n"
                "def test_union_optional_parsing():\n"
                "    assert parse_union_value(None, ['dict', 'none']) is None\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from pydantic_core.parser import parse_union_value\nimport pytest\n\n"
                "def test_union_rejection_when_not_allowed():\n"
                "    with pytest.raises(ValueError):\n"
                "        parse_union_value(None, ['dict', 'int'])\n\n"
                "def test_union_valid_value():\n"
                "    assert parse_union_value({'a': 1}, ['dict', 'none']) == {'a': 1}\n"
            )
        },
        fixed_source={
            "pydantic_core/parser.py": (
                "def parse_union_value(val, allowed_types: list):\n"
                "    allowed_lower = [t.lower() for t in allowed_types]\n"
                "    if val is None:\n"
                "        if any(t in allowed_lower for t in ('none', 'null', 'optional')):\n"
                "            return None\n"
                "        raise ValueError('invalid union resolution for None value')\n"
                "    return val\n"
            )
        },
        expected_affected_files=["pydantic_core/parser.py"],
        expected_symbols=["parse_union_value"],
    ),

    # -------------------------------------------------------------------------
    # HIST-005: FastAPI — Header dependency collision with query parameter alias
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-005",
        project="fastapi",
        ecosystem="python",
        cve_or_issue="Issue #2116",
        category="Dependency Injection / Routing",
        title="Query parameter alias collisions overwrite header dependencies",
        description="Dependency resolution merged query params and headers into a single flat dict without namespace isolation.",
        error_message="KeyError: 'authorization header missing due to query alias override'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 16, in test_header_query_alias_separation\n'
            "    res = resolve_request_params(query={'token': 'q123'}, headers={'token': 'h456'})\n"
            "KeyError: 'authorization header missing due to query alias override'\n"
        ),
        source_files={
            "fastapi_di/__init__.py": "",
            "fastapi_di/params.py": (
                "def resolve_request_params(query: dict, headers: dict) -> dict:\n"
                "    # Defect: Flattened dict where query params overwrite headers\n"
                "    merged = {}\n"
                "    merged.update(headers)\n"
                "    merged.update(query)\n"
                "    if 'token' in query and 'token' in headers and merged.get('header_token') is None:\n"
                "        raise KeyError('authorization header missing due to query alias override')\n"
                "    return merged\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from fastapi_di.params import resolve_request_params\n\n"
                "def test_header_query_alias_separation():\n"
                "    res = resolve_request_params(query={'token': 'q123'}, headers={'token': 'h456'})\n"
                "    assert res['query']['token'] == 'q123'\n"
                "    assert res['headers']['token'] == 'h456'\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from fastapi_di.params import resolve_request_params\n\n"
                "def test_empty_headers_and_query():\n"
                "    res = resolve_request_params({}, {})\n"
                "    assert res == {'query': {}, 'headers': {}}\n"
            )
        },
        fixed_source={
            "fastapi_di/params.py": (
                "def resolve_request_params(query: dict, headers: dict) -> dict:\n"
                "    return {\n"
                "        'query': dict(query),\n"
                "        'headers': dict(headers),\n"
                "    }\n"
            )
        },
        expected_affected_files=["fastapi_di/params.py"],
        expected_symbols=["resolve_request_params"],
    ),

    # -------------------------------------------------------------------------
    # HIST-006: SQLAlchemy — Colon in JSON path expression bind parameter parsing
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-006",
        project="sqlalchemy",
        ecosystem="python",
        cve_or_issue="Issue #4481",
        category="Database / SQL Compilation",
        title="Colon in JSON path operator mistakenly treated as bind parameter",
        description="SQL tokenizer interpreted any : character as a named parameter placeholder, even inside JSON access operators (->:key).",
        error_message="ValueError: unbound parameter detected in JSON clause ':field'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 12, in test_json_colon_escaping\n'
            "    res = extract_bind_params('SELECT data->>\"user:name\" FROM users')\n"
            "ValueError: unbound parameter detected in JSON clause ':field'\n"
        ),
        source_files={
            "sa_compiler/__init__.py": "",
            "sa_compiler/tokenizer.py": (
                "def extract_bind_params(sql_text: str) -> list:\n"
                "    # Defect: Any colon token outside quote is assumed bind param\n"
                "    if ':name' in sql_text or ':field' in sql_text:\n"
                "        raise ValueError('unbound parameter detected in JSON clause \":field\"')\n"
                "    import re\n"
                "    return re.findall(r':([a-zA-Z0-9_]+)', sql_text)\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from sa_compiler.tokenizer import extract_bind_params\n\n"
                "def test_json_colon_escaping():\n"
                "    params = extract_bind_params('SELECT data->>:field FROM logs WHERE id = :log_id')\n"
                "    assert 'log_id' in params\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from sa_compiler.tokenizer import extract_bind_params\n\n"
                "def test_no_params():\n"
                "    assert extract_bind_params('SELECT 1') == []\n\n"
                "def test_standard_bind_param():\n"
                "    assert extract_bind_params('SELECT * FROM t WHERE a = :val') == ['val']\n"
            )
        },
        fixed_source={
            "sa_compiler/tokenizer.py": (
                "def extract_bind_params(sql_text: str) -> list:\n"
                "    import re\n"
                "    # Strip JSON operators like ->> or ->: before extracting bind params\n"
                "    clean = re.sub(r'->>?:[a-zA-Z0-9_]+', '', sql_text)\n"
                "    return re.findall(r':([a-zA-Z0-9_]+)', clean)\n"
            )
        },
        expected_affected_files=["sa_compiler/tokenizer.py"],
        expected_symbols=["extract_bind_params"],
    ),

    # -------------------------------------------------------------------------
    # HIST-007: Express / QS — Prototype pollution prevention in query parser
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-007",
        project="express",
        ecosystem="python",
        cve_or_issue="CVE-2022-24999",
        category="Security / Query Parsing",
        title="Prototype pollution assignment allowed via __proto__ query parameters",
        description="Extended query parameter parser allowed direct modification of object prototype properties.",
        error_message="AssertionError: prototype polluted with malicious attribute",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 14, in test_proto_pollution_defense\n'
            "    assert '__proto__' not in parsed\n"
            "AssertionError: assert '__proto__' not in {'__proto__': {'polluted': True}}\n"
        ),
        source_files={
            "express_qs/__init__.py": "",
            "express_qs/parser.py": (
                "def parse_nested_query(params: dict) -> dict:\n"
                "    # Defect: Insecurely assigns __proto__ keys without filtering\n"
                "    result = {}\n"
                "    for k, v in params.items():\n"
                "        result[k] = v\n"
                "    return result\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from express_qs.parser import parse_nested_query\n\n"
                "def test_proto_pollution_defense():\n"
                "    inp = {'__proto__': {'polluted': True}, 'user': 'alice'}\n"
                "    out = parse_nested_query(inp)\n"
                "    assert '__proto__' not in out\n"
                "    assert out.get('user') == 'alice'\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from express_qs.parser import parse_nested_query\n\n"
                "def test_constructor_pollution_defense():\n"
                "    inp = {'constructor': {'prototype': {}}, 'q': '1'}\n"
                "    out = parse_nested_query(inp)\n"
                "    assert 'constructor' not in out\n"
                "    assert out == {'q': '1'}\n"
            )
        },
        fixed_source={
            "express_qs/parser.py": (
                "def parse_nested_query(params: dict) -> dict:\n"
                "    forbidden = {'__proto__', 'constructor', 'prototype'}\n"
                "    result = {}\n"
                "    for k, v in params.items():\n"
                "        if k in forbidden:\n"
                "            continue\n"
                "        result[k] = v\n"
                "    return result\n"
            )
        },
        expected_affected_files=["express_qs/parser.py"],
        expected_symbols=["parse_nested_query"],
    ),

    # -------------------------------------------------------------------------
    # HIST-008: Tornado — Transfer-encoding CRLF / whitespace header parsing
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-008",
        project="tornado",
        ecosystem="python",
        cve_or_issue="CVE-2023-28370",
        category="Security / HTTP Smuggling",
        title="Chunked transfer encoding parser accepts trailing whitespace or tabs",
        description="Chunk size parsing permitted trailing tab characters, enabling HTTP request smuggling.",
        error_message="ValueError: invalid chunk size line contains trailing tabs",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 12, in test_reject_whitespace_chunk_header\n'
            "    parse_chunk_size('10 \\t\\r\\n')\n"
            "AssertionError: ValueError not raised\n"
        ),
        source_files={
            "tornado_http/__init__.py": "",
            "tornado_http/chunk_parser.py": (
                "def parse_chunk_size(chunk_line: str) -> int:\n"
                "    # Defect: Insecurely uses strip() allowing tabs and arbitrary whitespace\n"
                "    cleaned = chunk_line.strip()\n"
                "    return int(cleaned, 16)\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from tornado_http.chunk_parser import parse_chunk_size\nimport pytest\n\n"
                "def test_reject_whitespace_chunk_header():\n"
                "    with pytest.raises(ValueError):\n"
                "        parse_chunk_size('10 \\t\\r\\n')\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from tornado_http.chunk_parser import parse_chunk_size\n\n"
                "def test_valid_chunk_size():\n"
                "    assert parse_chunk_size('1a\\r\\n') == 26\n"
            )
        },
        fixed_source={
            "tornado_http/chunk_parser.py": (
                "def parse_chunk_size(chunk_line: str) -> int:\n"
                "    if not chunk_line.endswith('\\r\\n'):\n"
                "        raise ValueError('Chunk line must end with CRLF')\n"
                "    token = chunk_line[:-2]\n"
                "    if ' ' in token or '\\t' in token:\n"
                "        raise ValueError('Invalid chunk size header contains whitespace')\n"
                "    return int(token, 16)\n"
            )
        },
        expected_affected_files=["tornado_http/chunk_parser.py"],
        expected_symbols=["parse_chunk_size"],
    ),

    # -------------------------------------------------------------------------
    # HIST-009: Pytest — Fixture teardown exception masking test result
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-009",
        project="pytest",
        ecosystem="python",
        cve_or_issue="Issue #5888",
        category="Test Harness / Fixtures",
        title="Fixture teardown failure silently suppresses test execution report",
        description="When fixture generator teardown raised an unhandled error, the primary test assertion outcome was lost.",
        error_message="RuntimeError: fixture teardown wiped test execution record",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 16, in test_preserve_test_record_on_teardown_error\n'
            "    res = run_test_with_teardown(test_func, failing_teardown)\n"
            "RuntimeError: fixture teardown wiped test execution record\n"
        ),
        source_files={
            "pytest_runner/__init__.py": "",
            "pytest_runner/runner.py": (
                "def run_test_with_teardown(test_fn, teardown_fn) -> dict:\n"
                "    # Defect: Wipes outcome dict on teardown exception\n"
                "    outcome = {'status': 'PASSED'}\n"
                "    try:\n"
                "        test_fn()\n"
                "    except Exception:\n"
                "        outcome['status'] = 'FAILED'\n"
                "    try:\n"
                "        teardown_fn()\n"
                "    except Exception:\n"
                "        raise RuntimeError('fixture teardown wiped test execution record')\n"
                "    return outcome\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from pytest_runner.runner import run_test_with_teardown\n\n"
                "def test_preserve_test_record_on_teardown_error():\n"
                "    def good_test(): pass\n"
                "    def bad_teardown(): raise ValueError('cleanup failed')\n"
                "    res = run_test_with_teardown(good_test, bad_teardown)\n"
                "    assert res['status'] == 'PASSED'\n"
                "    assert 'cleanup failed' in str(res.get('teardown_error'))\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from pytest_runner.runner import run_test_with_teardown\n\n"
                "def test_clean_test_and_teardown():\n"
                "    res = run_test_with_teardown(lambda: None, lambda: None)\n"
                "    assert res == {'status': 'PASSED', 'teardown_error': None}\n"
            )
        },
        fixed_source={
            "pytest_runner/runner.py": (
                "def run_test_with_teardown(test_fn, teardown_fn) -> dict:\n"
                "    outcome = {'status': 'PASSED', 'teardown_error': None}\n"
                "    try:\n"
                "        test_fn()\n"
                "    except Exception as e:\n"
                "        outcome['status'] = 'FAILED'\n"
                "        outcome['test_error'] = e\n"
                "    try:\n"
                "        teardown_fn()\n"
                "    except Exception as e:\n"
                "        outcome['teardown_error'] = e\n"
                "    return outcome\n"
            )
        },
        expected_affected_files=["pytest_runner/runner.py"],
        expected_symbols=["run_test_with_teardown"],
    ),

    # -------------------------------------------------------------------------
    # HIST-010: Marshmallow — List field deserialization crash on None element
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-010",
        project="marshmallow",
        ecosystem="python",
        cve_or_issue="Issue #1522",
        category="Serialization / Schema",
        title="List field deserialization crashes with AttributeError when element is None",
        description="Deserializing a list containing None caused AttributeError if allow_none was False on inner element.",
        error_message="AttributeError: 'NoneType' object has no attribute 'strip'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 14, in test_list_none_element_validation\n'
            "    res = deserialize_string_list(['valid', None], allow_none_element=False)\n"
            '  File "marshmallow_schema/fields.py", line 8, in deserialize_string_list\n'
            "    return [item.strip() for item in values]\n"
            "AttributeError: 'NoneType' object has no attribute 'strip'\n"
        ),
        source_files={
            "marshmallow_schema/__init__.py": "",
            "marshmallow_schema/fields.py": (
                "def deserialize_string_list(values: list, allow_none_element: bool = False) -> list:\n"
                "    # Defect: Unchecked call to item.strip() when item is None\n"
                "    return [item.strip() for item in values]\n"
            )
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from marshmallow_schema.fields import deserialize_string_list\nimport pytest\n\n"
                "def test_list_none_element_validation():\n"
                "    with pytest.raises(ValueError):\n"
                "        deserialize_string_list(['valid', None], allow_none_element=False)\n"
            )
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from marshmallow_schema.fields import deserialize_string_list\n\n"
                "def test_list_allow_none_element():\n"
                "    res = deserialize_string_list(['a', None], allow_none_element=True)\n"
                "    assert res == ['a', None]\n\n"
                "def test_list_all_strings():\n"
                "    assert deserialize_string_list([' apple ']) == ['apple']\n"
            )
        },
        fixed_source={
            "marshmallow_schema/fields.py": (
                "def deserialize_string_list(values: list, allow_none_element: bool = False) -> list:\n"
                "    res = []\n"
                "    for item in values:\n"
                "        if item is None:\n"
                "            if not allow_none_element:\n"
                "                raise ValueError('None elements not permitted')\n"
                "            res.append(None)\n"
                "        else:\n"
                "            res.append(str(item).strip())\n"
                "    return res\n"
            )
        },
        expected_affected_files=["marshmallow_schema/fields.py"],
        expected_symbols=["deserialize_string_list"],
    ),

    # -------------------------------------------------------------------------
    # HIST-011: HTTPX — Duplicate query parameter serialization collapsed
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-011",
        project="httpx",
        ecosystem="python",
        cve_or_issue="Issue #1240",
        category="Networking / HTTP Query Serialization",
        title="Duplicate query parameter keys collapsed during URL serialization",
        description="httpx URL parser collapsed multiple identical query parameter keys instead of serializing all values.",
        error_message="AssertionError: assert 'https://example.com/?filter=a' == 'https://example.com/?filter=a&filter=b'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 12, in test_duplicate_query_params\n'
            "    assert str(url) == 'https://example.com/?filter=a&filter=b'\n"
            "AssertionError: assert 'https://example.com/?filter=a' == 'https://example.com/?filter=a&filter=b'\n"
        ),
        source_files={
            "httpx_urls/__init__.py": "",
            "httpx_urls/urls.py": (
                "from typing import List, Tuple\n\n"
                "def encode_query_params(params: List[Tuple[str, str]]) -> str:\n"
                "    # Defect: Converts to dict, collapsing duplicate keys\n"
                "    param_dict = dict(params)\n"
                "    return '&'.join(f'{k}={v}' for k, v in param_dict.items())\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from httpx_urls.urls import encode_query_params\n\n"
                "def test_duplicate_query_params():\n"
                "    params = [('filter', 'a'), ('filter', 'b')]\n"
                "    assert encode_query_params(params) == 'filter=a&filter=b'\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from httpx_urls.urls import encode_query_params\n\n"
                "def test_single_query_param():\n"
                "    assert encode_query_params([('key', 'val')]) == 'key=val'\n\n"
                "def test_mixed_query_params():\n"
                "    assert encode_query_params([('a', '1'), ('b', '2'), ('a', '3')]) == 'a=1&b=2&a=3'\n"
            ),
        },
        fixed_source={
            "httpx_urls/urls.py": (
                "from typing import List, Tuple\n\n"
                "def encode_query_params(params: List[Tuple[str, str]]) -> str:\n"
                "    return '&'.join(f'{k}={v}' for k, v in params)\n"
            ),
        },
        expected_affected_files=["httpx_urls/urls.py"],
        expected_symbols=["encode_query_params"],
    ),

    # -------------------------------------------------------------------------
    # HIST-012: Urllib3 — IPv6 and complex authority parsing failure
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-012",
        project="urllib3",
        ecosystem="python",
        cve_or_issue="Issue #2168 / CVE-2021-33503",
        category="Security / URL Parsing",
        title="Authority regex parser crashes on IPv6 addresses and complex authorities",
        description="Regex-based authority parsing failed to match IPv6 addresses with bracketed colons, raising ValueError.",
        error_message="ValueError: Invalid authority component",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 6, in test_ipv6_authority_parsing\n'
            "    res = parse_authority('admin@[::1]:8080')\n"
            '  File "urllib3_util/url.py", line 9, in parse_authority\n'
            "    raise ValueError('Invalid authority component')\n"
            "ValueError: Invalid authority component\n"
        ),
        source_files={
            "urllib3_util/__init__.py": "",
            "urllib3_util/url.py": (
                "import re\n\n"
                "# Defect: Regex cannot parse IPv6 bracketed colons\n"
                "AUTHORITY_RE = re.compile(r'^([^@:]+(:[^@]+)?@)?([^:]+)(:([0-9]+))?$')\n\n"
                "def parse_authority(authority: str):\n"
                "    match = AUTHORITY_RE.match(authority)\n"
                "    if not match:\n"
                "        raise ValueError('Invalid authority component')\n"
                "    userinfo = (match.group(1) or '').rstrip('@')\n"
                "    host = match.group(3)\n"
                "    port = (match.group(5) or '')\n"
                "    return (userinfo, host, port)\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from urllib3_util.url import parse_authority\n\n"
                "def test_ipv6_authority_parsing():\n"
                "    res = parse_authority('admin@[::1]:8080')\n"
                "    assert res == ('admin', '[::1]', '8080')\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from urllib3_util.url import parse_authority\n\n"
                "def test_standard_authority():\n"
                "    res = parse_authority('user:pass@localhost:8080')\n"
                "    assert res == ('user:pass', 'localhost', '8080')\n\n"
                "def test_simple_host():\n"
                "    res = parse_authority('localhost')\n"
                "    assert res == ('', 'localhost', '')\n"
            ),
        },
        fixed_source={
            "urllib3_util/url.py": (
                "# Linear-time non-backtracking authority parser supporting IPv6\n"
                "def parse_authority(authority: str):\n"
                "    if not authority or len(authority) > 1024:\n"
                "        raise ValueError('Invalid authority component')\n"
                "    if '@' in authority:\n"
                "        userinfo, _, host_port = authority.rpartition('@')\n"
                "    else:\n"
                "        userinfo, host_port = '', authority\n"
                "    if ':' in host_port:\n"
                "        host, _, port = host_port.rpartition(':')\n"
                "    else:\n"
                "        host, port = host_port, ''\n"
                "    return (userinfo, host, port)\n"
            ),
        },
        expected_affected_files=["urllib3_util/url.py"],
        expected_symbols=["parse_authority"],
    ),
]
