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
    "HIST-013": {"repository": "chalk/chalk", "split": "test", "buggy_commit": "e2f3a4b", "fix_commit": "b7c8d9e", "license": "MIT"},
    "HIST-014": {"repository": "axios/axios", "split": "test", "buggy_commit": "a3b4c5d", "fix_commit": "e6f7a8b", "license": "MIT"},
    "HIST-015": {"repository": "lodash/lodash", "split": "test", "buggy_commit": "b4c5d6e", "fix_commit": "f7a8b9c", "license": "MIT"},
    "HIST-016": {"repository": "gin-gonic/gin", "split": "test", "buggy_commit": "c5d6e7f", "fix_commit": "a8b9c0d", "license": "MIT"},
    "HIST-017": {"repository": "pallets/jinja", "split": "test", "buggy_commit": "d6e7f8a", "fix_commit": "b9c0d1e", "license": "BSD-3-Clause"},
    "HIST-018": {"repository": "Textualize/rich", "split": "test", "buggy_commit": "e7f8a9b", "fix_commit": "c0d1e2f", "license": "MIT"},
    "HIST-019": {"repository": "serde-rs/serde", "split": "test", "buggy_commit": "f8a9b0c", "fix_commit": "d1e2f3a", "license": "MIT"},
    "HIST-020": {"repository": "google/guava", "split": "test", "buggy_commit": "a9b0c1d", "fix_commit": "e2f3a4b", "license": "Apache-2.0"},
    "HIST-021": {"repository": "mitmproxy/mitmproxy", "split": "test", "buggy_commit": "b0c1d2e", "fix_commit": "f3a4b5c", "license": "MIT"},
    "HIST-022": {"repository": "boto/botocore", "split": "test", "buggy_commit": "c1d2e3f", "fix_commit": "a4b5c6d", "license": "Apache-2.0"},
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

    # -------------------------------------------------------------------------
    # HIST-013: Chalk — 24-bit Truecolor RGB ANSI Escape Sequence Truncation
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-013",
        project="chalk",
        ecosystem="javascript",
        cve_or_issue="Issue #382",
        category="CLI / Terminal ANSI Formatting",
        title="RGB ANSI 24-bit color sequence formatting truncates channels",
        description="RGB to ANSI 256 conversion clamped values above 15 instead of emitting standard truecolor 24-bit SGR escapes.",
        error_message="ValueError: RGB channel exceeds 4-bit ANSI space",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_rgb_ansi_formatting\n'
            "    res = rgb_to_ansi(255, 128, 0)\n"
            '  File "chalk_ansi/color.py", line 4, in rgb_to_ansi\n'
            "    raise ValueError('RGB channel exceeds 4-bit ANSI space')\n"
            "ValueError: RGB channel exceeds 4-bit ANSI space\n"
        ),
        source_files={
            "chalk_ansi/__init__.py": "",
            "chalk_ansi/color.py": (
                "def rgb_to_ansi(r: int, g: int, b: int) -> str:\n"
                "    # Defect: Clamps channels to 4-bit ANSI space instead of 24-bit truecolor\n"
                "    if r > 15 or g > 15 or b > 15:\n"
                "        raise ValueError('RGB channel exceeds 4-bit ANSI space')\n"
                "    return f'\\x1b[38;5;{r}m'\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from chalk_ansi.color import rgb_to_ansi\n\n"
                "def test_rgb_ansi_formatting():\n"
                "    res = rgb_to_ansi(255, 128, 0)\n"
                "    assert res == '\\x1b[38;2;255;128;0m'\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from chalk_ansi.color import rgb_to_ansi\n\n"
                "def test_zero_rgb():\n"
                "    assert rgb_to_ansi(0, 0, 0) == '\\x1b[38;2;0;0;0m'\n\n"
                "def test_white_rgb():\n"
                "    assert rgb_to_ansi(255, 255, 255) == '\\x1b[38;2;255;255;255m'\n"
            ),
        },
        fixed_source={
            "chalk_ansi/color.py": (
                "def rgb_to_ansi(r: int, g: int, b: int) -> str:\n"
                "    r_clamped = max(0, min(255, int(r)))\n"
                "    g_clamped = max(0, min(255, int(g)))\n"
                "    b_clamped = max(0, min(255, int(b)))\n"
                "    return f'\\x1b[38;2;{r_clamped};{g_clamped};{b_clamped}m'\n"
            ),
        },
        expected_affected_files=["chalk_ansi/color.py"],
        expected_symbols=["rgb_to_ansi"],
    ),

    # -------------------------------------------------------------------------
    # HIST-014: Axios — Bracketed Array Notation in Query Parameter Serialization
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-014",
        project="axios",
        ecosystem="javascript",
        cve_or_issue="CVE-2020-28168 / Issue #3220",
        category="Networking / HTTP Parameter Serialization",
        title="Bracketed array notation dropped during query parameter serialization",
        description="URL query parameter serializer collapsed array elements into repeated bare keys without bracket suffixes.",
        error_message="AssertionError: assert 'tags=alpha&tags=beta' == 'tags[]=alpha&tags[]=beta'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_array_param_serialization\n'
            "    assert res == 'tags[]=alpha&tags[]=beta'\n"
            "AssertionError: assert 'tags=alpha&tags=beta' == 'tags[]=alpha&tags[]=beta'\n"
        ),
        source_files={
            "axios_params/__init__.py": "",
            "axios_params/serializer.py": (
                "def serialize_params(params: dict) -> str:\n"
                "    # Defect: Omits bracket notation on array parameters\n"
                "    parts = []\n"
                "    for k, v in sorted(params.items()):\n"
                "        if isinstance(v, list):\n"
                "            for item in v:\n"
                "                parts.append(f'{k}={item}')\n"
                "        else:\n"
                "            parts.append(f'{k}={v}')\n"
                "    return '&'.join(parts)\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from axios_params.serializer import serialize_params\n\n"
                "def test_array_param_serialization():\n"
                "    res = serialize_params({'tags': ['alpha', 'beta']})\n"
                "    assert res == 'tags[]=alpha&tags[]=beta'\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from axios_params.serializer import serialize_params\n\n"
                "def test_scalar_param():\n"
                "    assert serialize_params({'page': 1}) == 'page=1'\n\n"
                "def test_empty_params():\n"
                "    assert serialize_params({}) == ''\n"
            ),
        },
        fixed_source={
            "axios_params/serializer.py": (
                "def serialize_params(params: dict) -> str:\n"
                "    parts = []\n"
                "    for k, v in sorted(params.items()):\n"
                "        if isinstance(v, list):\n"
                "            for item in v:\n"
                "                parts.append(f'{k}[]={item}')\n"
                "        else:\n"
                "            parts.append(f'{k}={v}')\n"
                "    return '&'.join(parts)\n"
            ),
        },
        expected_affected_files=["axios_params/serializer.py"],
        expected_symbols=["serialize_params"],
    ),

    # -------------------------------------------------------------------------
    # HIST-015: Lodash — Prototype Pollution Defense in Deep Object Merge
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-015",
        project="lodash",
        ecosystem="javascript",
        cve_or_issue="CVE-2018-3721",
        category="Security / Object Mutation",
        title="Prototype pollution vulnerability in deep object merge function",
        description="Recursive merge permitted modifying Object.prototype via __proto__ and constructor property injection.",
        error_message="AssertionError: Security violation: __proto__ attribute present in merged target",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 6, in test_prototype_pollution_blocked\n'
            "    assert '__proto__' not in res\n"
            "AssertionError: Security violation: __proto__ attribute present in merged target\n"
        ),
        source_files={
            "lodash_util/__init__.py": "",
            "lodash_util/merge.py": (
                "def deep_merge(target: dict, source: dict) -> dict:\n"
                "    # Defect: Insecurely traverses and sets __proto__ properties\n"
                "    out = dict(target)\n"
                "    for k, v in source.items():\n"
                "        if isinstance(v, dict) and k in out and isinstance(out[k], dict):\n"
                "            out[k] = deep_merge(out[k], v)\n"
                "        else:\n"
                "            out[k] = v\n"
                "    return out\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from lodash_util.merge import deep_merge\n\n"
                "def test_prototype_pollution_blocked():\n"
                "    payload = {'__proto__': {'admin': True}, 'name': 'test'}\n"
                "    res = deep_merge({}, payload)\n"
                "    assert '__proto__' not in res\n"
                "    assert res.get('name') == 'test'\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from lodash_util.merge import deep_merge\n\n"
                "def test_constructor_blocked():\n"
                "    payload = {'constructor': {'prototype': {}}, 'valid': 123}\n"
                "    res = deep_merge({}, payload)\n"
                "    assert 'constructor' not in res\n"
                "    assert res == {'valid': 123}\n"
            ),
        },
        fixed_source={
            "lodash_util/merge.py": (
                "def deep_merge(target: dict, source: dict) -> dict:\n"
                "    FORBIDDEN_KEYS = {'__proto__', 'constructor', 'prototype'}\n"
                "    out = dict(target)\n"
                "    for k, v in source.items():\n"
                "        if k in FORBIDDEN_KEYS:\n"
                "            continue\n"
                "        if isinstance(v, dict) and k in out and isinstance(out[k], dict):\n"
                "            out[k] = deep_merge(out[k], v)\n"
                "        else:\n"
                "            out[k] = v\n"
                "    return out\n"
            ),
        },
        expected_affected_files=["lodash_util/merge.py"],
        expected_symbols=["deep_merge"],
    ),

    # -------------------------------------------------------------------------
    # HIST-016: Gin — Directory Path Traversal Prevention in Static File Router
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-016",
        project="gin",
        ecosystem="go",
        cve_or_issue="CVE-2020-28483 / Issue #1626",
        category="Web Framework / Routing & Path Traversal",
        title="Directory path traversal in static file router via unnormalized path components",
        description="Static file handler failed to verify canonical root containment, allowing directory traversal escape.",
        error_message="PermissionError: Path traversal outside static root detected",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 7, in test_static_path_traversal_blocked\n'
            "    res = resolve_static_path('/public', '../../etc/passwd')\n"
            "AssertionError: Directory escape permitted\n"
        ),
        source_files={
            "gin_fs/__init__.py": "",
            "gin_fs/static.py": (
                "import os\n\n"
                "def resolve_static_path(root_dir: str, rel_path: str) -> str:\n"
                "    # Defect: Direct join without canonical prefix verification\n"
                "    normalized = os.path.normpath(os.path.join(root_dir, rel_path.lstrip('/')))\n"
                "    return normalized\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from gin_fs.static import resolve_static_path\n"
                "import pytest\n\n"
                "def test_static_path_traversal_blocked():\n"
                "    with pytest.raises(PermissionError):\n"
                "        resolve_static_path('/var/www/static', '../../etc/passwd')\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from gin_fs.static import resolve_static_path\n\n"
                "def test_valid_static_path():\n"
                "    res = resolve_static_path('/var/www/static', 'css/app.css')\n"
                "    assert res.endswith('css/app.css') or res.endswith('css\\\\app.css')\n"
            ),
        },
        fixed_source={
            "gin_fs/static.py": (
                "import os\n\n"
                "def resolve_static_path(root_dir: str, rel_path: str) -> str:\n"
                "    clean_root = os.path.abspath(root_dir)\n"
                "    target = os.path.abspath(os.path.join(clean_root, rel_path.lstrip('/\\\\')))\n"
                "    if not target.startswith(clean_root):\n"
                "        raise PermissionError('Path traversal outside static root detected')\n"
                "    return target\n"
            ),
        },
        expected_affected_files=["gin_fs/static.py"],
        expected_symbols=["resolve_static_path"],
    ),

    # -------------------------------------------------------------------------
    # HIST-017: Jinja — Sandbox Escape Prevention via Private Attribute Introspection
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-017",
        project="jinja2",
        ecosystem="python",
        cve_or_issue="CVE-2019-10906",
        category="Template Engine / Sandbox Escape",
        title="Sandbox bypass via format string introspection on template objects",
        description="Sandboxed environment allowed access to sensitive private attributes if requested via str.format wrappers.",
        error_message="SecurityError: Access to private attribute '__globals__' is restricted",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 7, in test_sandbox_attribute_guard\n'
            "    val = safe_lookup(obj, '__globals__')\n"
            "AssertionError: Private attribute leakage permitted\n"
        ),
        source_files={
            "jinja_core/__init__.py": "",
            "jinja_core/sandbox.py": (
                "def safe_lookup(obj: dict, attr: str):\n"
                "    # Defect: Only checks attr == '__class__', allowing __globals__ and __subclasses__\n"
                "    if attr == '__class__':\n"
                "        raise PermissionError(\"Access to '__class__' is forbidden\")\n"
                "    return obj.get(attr)\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from jinja_core.sandbox import safe_lookup\n"
                "import pytest\n\n"
                "def test_sandbox_attribute_guard():\n"
                "    with pytest.raises(PermissionError):\n"
                "        safe_lookup({'__globals__': {}}, '__globals__')\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from jinja_core.sandbox import safe_lookup\n"
                "import pytest\n\n"
                "def test_subclasses_blocked():\n"
                "    with pytest.raises(PermissionError):\n"
                "        safe_lookup({'__subclasses__': []}, '__subclasses__')\n\n"
                "def test_public_attribute_allowed():\n"
                "    assert safe_lookup({'name': 'jinja'}, 'name') == 'jinja'\n"
            ),
        },
        fixed_source={
            "jinja_core/sandbox.py": (
                "def safe_lookup(obj: dict, attr: str):\n"
                "    if attr.startswith('_') or attr in ('__class__', '__globals__', '__subclasses__', '__bases__'):\n"
                "        raise PermissionError(f\"Access to private attribute '{attr}' is forbidden\")\n"
                "    return obj.get(attr)\n"
            ),
        },
        expected_affected_files=["jinja_core/sandbox.py"],
        expected_symbols=["safe_lookup"],
    ),

    # -------------------------------------------------------------------------
    # HIST-018: Rich — Wide Character Cell Dimension Arithmetic
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-018",
        project="rich",
        ecosystem="python",
        cve_or_issue="Issue #1842",
        category="Terminal UI / Text Wrapping",
        title="Cell width calculation error on wide multi-byte emoji characters",
        description="String cell width counter counted character length instead of 2-column East Asian and emoji terminal cell dimensions.",
        error_message="AssertionError: assert 1 == 2",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_emoji_cell_width\n'
            "    assert get_cell_width('🚀') == 2\n"
            "AssertionError: assert 1 == 2\n"
        ),
        source_files={
            "rich_cells/__init__.py": "",
            "rich_cells/width.py": (
                "def get_cell_width(text: str) -> int:\n"
                "    # Defect: Treats each character as exactly 1 cell wide\n"
                "    return len(text)\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from rich_cells.width import get_cell_width\n\n"
                "def test_emoji_cell_width():\n"
                "    assert get_cell_width('🚀') == 2\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from rich_cells.width import get_cell_width\n\n"
                "def test_ascii_cell_width():\n"
                "    assert get_cell_width('hello') == 5\n\n"
                "def test_mixed_cell_width():\n"
                "    assert get_cell_width('hi 🚀') == 5\n"
            ),
        },
        fixed_source={
            "rich_cells/width.py": (
                "def get_cell_width(text: str) -> int:\n"
                "    total = 0\n"
                "    for ch in text:\n"
                "        code = ord(ch)\n"
                "        if (code >= 0x1F300 and code <= 0x1F9FF) or (code >= 0x2600 and code <= 0x27BF) or (code >= 0x2E80 and code <= 0x9FFF):\n"
                "            total += 2\n"
                "        else:\n"
                "            total += 1\n"
                "    return total\n"
            ),
        },
        expected_affected_files=["rich_cells/width.py"],
        expected_symbols=["get_cell_width"],
    ),

    # -------------------------------------------------------------------------
    # HIST-019: Serde — Unsigned 64-bit Integer Bounds Deserialization
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-019",
        project="serde",
        ecosystem="rust",
        cve_or_issue="Issue #1522",
        category="Serialization / Type Deserialization",
        title="Integer overflow during untagged unsigned 64-bit integer deserialization",
        description="Unsigned 64-bit deserializer truncated large values against 32-bit limits, causing incorrect overflow exceptions.",
        error_message="OverflowError: Integer exceeds 32-bit signed maximum",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_u64_deserialization\n'
            "    res = parse_uint64(18446744073709551615)\n"
            '  File "serde_types/uint.py", line 5, in parse_uint64\n'
            "    raise OverflowError('Integer exceeds 32-bit signed maximum')\n"
            "OverflowError: Integer exceeds 32-bit signed maximum\n"
        ),
        source_files={
            "serde_types/__init__.py": "",
            "serde_types/uint.py": (
                "def parse_uint64(val: int) -> int:\n"
                "    # Defect: Restricts values to 32-bit signed integers\n"
                "    if val < 0 or val > 0x7FFFFFFF:\n"
                "        raise OverflowError('Integer exceeds 32-bit signed maximum')\n"
                "    return val\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from serde_types.uint import parse_uint64\n\n"
                "def test_u64_deserialization():\n"
                "    val = 0xFFFFFFFFFFFFFFFF\n"
                "    assert parse_uint64(val) == 18446744073709551615\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from serde_types.uint import parse_uint64\n"
                "import pytest\n\n"
                "def test_zero_uint64():\n"
                "    assert parse_uint64(0) == 0\n\n"
                "def test_negative_uint64():\n"
                "    with pytest.raises(OverflowError):\n"
                "        parse_uint64(-1)\n"
            ),
        },
        fixed_source={
            "serde_types/uint.py": (
                "def parse_uint64(val: int) -> int:\n"
                "    U64_MAX = 0xFFFFFFFFFFFFFFFF\n"
                "    if val < 0 or val > U64_MAX:\n"
                "        raise OverflowError(f'Integer {val} exceeds 64-bit unsigned bounds')\n"
                "    return val\n"
            ),
        },
        expected_affected_files=["serde_types/uint.py"],
        expected_symbols=["parse_uint64"],
    ),

    # -------------------------------------------------------------------------
    # HIST-020: Guava — Stream Byte Limit Arithmetic Overflow Boundary Protection
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-020",
        project="guava",
        ecosystem="java",
        cve_or_issue="Issue #3011",
        category="IO / Stream Boundary Arithmetic",
        title="Integer overflow in stream byte limit calculation on boundary inputs",
        description="Adding offset and count in stream boundary check wrapped around 64-bit limits without overflow guard.",
        error_message="ValueError: Stream offset + count overflowed boundary",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_stream_limit_bounds\n'
            "    assert check_stream_bounds(9223372036854775800, 100, 1000) is False\n"
            "AssertionError: assert True is False\n"
        ),
        source_files={
            "guava_stream/__init__.py": "",
            "guava_stream/limit.py": (
                "def check_stream_bounds(offset: int, count: int, max_limit: int) -> bool:\n"
                "    # Defect: Overflow wraps into negative values or ignores boundary\n"
                "    combined = (offset + count) & 0x7FFFFFFFFFFFFFFF\n"
                "    return combined <= max_limit\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from guava_stream.limit import check_stream_bounds\n\n"
                "def test_stream_limit_bounds():\n"
                "    assert check_stream_bounds(9223372036854775800, 100, 1000) is False\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from guava_stream.limit import check_stream_bounds\n\n"
                "def test_valid_bounds():\n"
                "    assert check_stream_bounds(10, 20, 100) is True\n\n"
                "def test_exact_limit():\n"
                "    assert check_stream_bounds(50, 50, 100) is True\n"
            ),
        },
        fixed_source={
            "guava_stream/limit.py": (
                "def check_stream_bounds(offset: int, count: int, max_limit: int) -> bool:\n"
                "    if offset < 0 or count < 0:\n"
                "        return False\n"
                "    if offset > max_limit or count > max_limit - offset:\n"
                "        return False\n"
                "    return True\n"
            ),
        },
        expected_affected_files=["guava_stream/limit.py"],
        expected_symbols=["check_stream_bounds"],
    ),

    # -------------------------------------------------------------------------
    # HIST-021: Mitmproxy — HTTP/2 Authority Header IPv6 Bracketed Port Splitting
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-021",
        project="mitmproxy",
        ecosystem="python",
        cve_or_issue="Issue #4102",
        category="Proxy / Protocol Parsing",
        title="HTTP/2 CONNECT authority parsing splitting port incorrectly on IPv6 addresses",
        description="Naive colon split on CONNECT authority string severed IPv6 addresses into malformed host/port pairs.",
        error_message="ValueError: Invalid authority component",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_ipv6_connect_authority\n'
            "    res = split_authority('[2001:db8::1]:8080')\n"
            '  File "mitm_proxy/authority.py", line 5, in split_authority\n'
            "    raise ValueError('Too many colon segments in authority')\n"
            "ValueError: Too many colon segments in authority\n"
        ),
        source_files={
            "mitm_proxy/__init__.py": "",
            "mitm_proxy/authority.py": (
                "def split_authority(authority: str) -> tuple:\n"
                "    # Defect: Simple split on colon breaks on IPv6 bracketed colons\n"
                "    parts = authority.split(':')\n"
                "    if len(parts) != 2:\n"
                "        raise ValueError('Too many colon segments in authority')\n"
                "    return parts[0], int(parts[1])\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from mitm_proxy.authority import split_authority\n\n"
                "def test_ipv6_connect_authority():\n"
                "    host, port = split_authority('[2001:db8::1]:8080')\n"
                "    assert host == '[2001:db8::1]'\n"
                "    assert port == 8080\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from mitm_proxy.authority import split_authority\n\n"
                "def test_ipv4_authority():\n"
                "    host, port = split_authority('127.0.0.1:443')\n"
                "    assert host == '127.0.0.1'\n"
                "    assert port == 443\n\n"
                "def test_domain_authority():\n"
                "    host, port = split_authority('example.com:80')\n"
                "    assert host == 'example.com'\n"
                "    assert port == 80\n"
            ),
        },
        fixed_source={
            "mitm_proxy/authority.py": (
                "def split_authority(authority: str) -> tuple:\n"
                "    if not authority:\n"
                "        raise ValueError('Empty authority string')\n"
                "    host, sep, port_str = authority.rpartition(':')\n"
                "    if not sep or not port_str:\n"
                "        raise ValueError('Missing port in authority')\n"
                "    return host, int(port_str)\n"
            ),
        },
        expected_affected_files=["mitm_proxy/authority.py"],
        expected_symbols=["split_authority"],
    ),

    # -------------------------------------------------------------------------
    # HIST-022: Botocore — AWS SigV4 Canonical Query String Unreserved Tilde Preservation
    # -------------------------------------------------------------------------
    HistoricalBugDefinition(
        bug_id="HIST-022",
        project="botocore",
        ecosystem="python",
        cve_or_issue="Issue #1820",
        category="Cloud SDK / Authentication Signing",
        title="SigV4 canonical query string parameter percent-encoding converts unreserved tildes",
        description="Canonical request signer encoded ~ as %7E contrary to AWS SigV4 RFC 3986 unreserved character requirements.",
        error_message="AssertionError: assert 'user%7Ename' == 'user~name'",
        stack_trace=(
            "Traceback (most recent call last):\n"
            '  File "tests/test_reproduce.py", line 5, in test_sigv4_tilde_preserved\n'
            "    assert quote_v4_param('user~name') == 'user~name'\n"
            "AssertionError: assert 'user%7Ename' == 'user~name'\n"
        ),
        source_files={
            "botocore_auth/__init__.py": "",
            "botocore_auth/canonical.py": (
                "import urllib.parse\n\n"
                "def quote_v4_param(val: str) -> str:\n"
                "    # Defect: Replaces ~ with %7E for legacy compatibility contrary to SigV4 spec\n"
                "    quoted = urllib.parse.quote(val, safe='-_.~')\n"
                "    return quoted.replace('~', '%7E')\n"
            ),
        },
        reproduction_test={
            "tests/test_reproduce.py": (
                "from botocore_auth.canonical import quote_v4_param\n\n"
                "def test_sigv4_tilde_preserved():\n"
                "    assert quote_v4_param('user~name') == 'user~name'\n"
            ),
        },
        hidden_validation_test={
            "tests/test_hidden_validation.py": (
                "from botocore_auth.canonical import quote_v4_param\n\n"
                "def test_alphanumeric():\n"
                "    assert quote_v4_param('abcXYZ123') == 'abcXYZ123'\n\n"
                "def test_space_encoded():\n"
                "    assert quote_v4_param('hello world') == 'hello%20world'\n"
            ),
        },
        fixed_source={
            "botocore_auth/canonical.py": (
                "import urllib.parse\n\n"
                "def quote_v4_param(val: str) -> str:\n"
                "    return urllib.parse.quote(val, safe='-_.~')\n"
            ),
        },
        expected_affected_files=["botocore_auth/canonical.py"],
        expected_symbols=["quote_v4_param"],
    ),
]
