"""Devaura Phase 8.1 Adversarial Benchmark Cases.

Defines 11 challenging, adversarial benchmark bugs (BUG-026 through BUG-036):
- BUG-026: Decoy Evidence (Stack trace points to decoy helper, real defect in data parser)
- BUG-027: Same-Name Functions (Multiple modules have identical function names)
- BUG-028: Multi-File Regression (Schema drift between producer and consumer across files)
- BUG-029: Incorrect Recent Commit (Git blame shows recent commit on unrelated module)
- BUG-030: Misleading Test Name (Test name suggests caching, defect in session store)
- BUG-031: Import / Dependency Failure (Missing critical standard library import)
- BUG-032: Type / Interface Regression (Producer returns dict, consumer expects attribute access)
- BUG-033: Partial Fix Trap (Trivial fix passes visible test but fails hidden edge-cases)
- BUG-034: Dynamic Dispatch (Dynamic getattr invocation hides call graph from static AST)
- BUG-035: Cross-Layer Failure (Missing null handling between database and API layers)
- BUG-036: False Repair Trap (Evaluates cheat detection when test files or assertions are weakened)
"""

from typing import Any, Dict, List

ADVERSARIAL_BUGS: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # BUG-026: Decoy Evidence
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-026",
        "category": "Adversarial-DecoyEvidence",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AttributeError",
        "failure_description": "AttributeError in formatter helper caused by empty token returned by parser.",
        "expected_root_cause": {
            "files": ["app/parser.py"],
            "symbols": ["extract_token"],
            "lines": [4],
        },
        "expected_fix_scope": ["app/parser.py"],
        "verification_command": "pytest test_pipeline.py",
        "expected_behavior": "Parser extract_token returns empty string instead of None when token parameter is absent.",
        "source_files": {
            "app/formatter.py": """def format_output(data):
    # Innocent decoy helper
    return f"Output: {data.strip()}"
""",
            "app/parser.py": """def extract_token(raw_input):
    if not raw_input or "token=" not in raw_input:
        return None
    return raw_input.split("token=")[1].split(";")[0]
""",
            "test_pipeline.py": """from app.formatter import format_output
from app.parser import extract_token

def test_valid_token():
    assert format_output(extract_token("token=abc;123")) == "Output: abc"

def test_missing_token():
    assert format_output(extract_token("no_token_here")) == "Output: "
""",
        },
        "fixed_files": {
            "app/parser.py": """def extract_token(raw_input):
    if not raw_input or "token=" not in raw_input:
        return ""
    return raw_input.split("token=")[1].split(";")[0]
""",
        },
        "hidden_tests": {
            "hidden_test_pipeline.py": """from app.formatter import format_output
from app.parser import extract_token

def test_hidden_empty_string():
    assert format_output(extract_token("")) == "Output: "

def test_hidden_none_input():
    assert format_output(extract_token(None)) == "Output: "

def test_hidden_whitespace_only():
    assert format_output(extract_token("   ")) == "Output: "

def test_hidden_multiple_semicolons():
    assert format_output(extract_token("token=xyz;foo;bar")) == "Output: xyz"
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-027: Same-Name Functions
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-027",
        "category": "Adversarial-SameNameFunctions",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "KeyError",
        "failure_description": "KeyError in database.get_user when queried with missing user ID.",
        "expected_root_cause": {
            "files": ["app/database.py"],
            "symbols": ["get_user"],
            "lines": [3],
        },
        "expected_fix_scope": ["app/database.py"],
        "verification_command": "pytest test_db.py",
        "expected_behavior": "database.get_user returns None instead of raising KeyError on unknown user ID.",
        "source_files": {
            "app/users.py": """def get_user(user_id):
    return {"id": user_id, "name": f"User_{user_id}"}
""",
            "app/database.py": """DB_RECORDS = {1: "Alice", 2: "Bob"}

def get_user(user_id):
    return DB_RECORDS[user_id]
""",
            "test_db.py": """from app.database import get_user

def test_get_existing_user():
    assert get_user(1) == "Alice"

def test_get_missing_user():
    assert get_user(99) is None
""",
        },
        "fixed_files": {
            "app/database.py": """DB_RECORDS = {1: "Alice", 2: "Bob"}

def get_user(user_id):
    return DB_RECORDS.get(user_id)
""",
        },
        "hidden_tests": {
            "hidden_test_db.py": """from app.database import get_user

def test_hidden_negative_id():
    assert get_user(-1) is None

def test_hidden_zero_id():
    assert get_user(0) is None

def test_hidden_second_user():
    assert get_user(2) == "Bob"
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-028: Multi-File Regression
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-028",
        "category": "Adversarial-MultiFileRegression",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "KeyError",
        "failure_description": "KeyError 'authorization' in client after auth_header schema migration.",
        "expected_root_cause": {
            "files": ["app/client.py"],
            "symbols": ["send_request"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/client.py"],
        "verification_command": "pytest test_client.py",
        "expected_behavior": "client.send_request handles both modern x-api-key and legacy authorization headers.",
        "source_files": {
            "app/auth_header.py": """def make_headers(api_key):
    # Schema migrated to x-api-key
    return {"x-api-key": api_key}
""",
            "app/client.py": """from app.auth_header import make_headers

def send_request(key):
    headers = make_headers(key)
    return headers["authorization"]
""",
            "test_client.py": """from app.client import send_request

def test_send():
    assert send_request("secret_key_123") == "secret_key_123"
""",
        },
        "fixed_files": {
            "app/client.py": """from app.auth_header import make_headers

def send_request(key):
    headers = make_headers(key)
    return headers.get("x-api-key") or headers.get("authorization", "")
""",
        },
        "hidden_tests": {
            "hidden_test_client.py": """from app.client import send_request

def test_hidden_empty_key():
    assert send_request("") == ""

def test_hidden_special_chars():
    assert send_request("key_!@#") == "key_!@#"
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-029: Incorrect Recent Commit / Blame Decoy
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-029",
        "category": "Adversarial-IncorrectRecentCommit",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "ValueError",
        "failure_description": "ValueError: invalid literal for int() in parse_and_multiply when given float string.",
        "expected_root_cause": {
            "files": ["app/calculator.py"],
            "symbols": ["parse_and_multiply"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/calculator.py"],
        "verification_command": "pytest test_calc.py",
        "expected_behavior": "parse_and_multiply parses numeric string as float before multiplying.",
        "source_files": {
            "app/analytics.py": """# Recent commit touched analytics.py
METRICS_COUNTER = 100
def log_event(name):
    return f"Logged {name}"
""",
            "app/calculator.py": """def parse_and_multiply(val_str, factor):
    return int(val_str) * factor
""",
            "test_calc.py": """from app.calculator import parse_and_multiply

def test_int():
    assert parse_and_multiply("4", 2) == 8

def test_float_string():
    assert parse_and_multiply("2.5", 2) == 5.0
""",
        },
        "fixed_files": {
            "app/calculator.py": """def parse_and_multiply(val_str, factor):
    return float(val_str) * factor
""",
        },
        "hidden_tests": {
            "hidden_test_calc.py": """from app.calculator import parse_and_multiply

def test_hidden_zero():
    assert parse_and_multiply("0.0", 5) == 0.0

def test_hidden_negative():
    assert parse_and_multiply("-3.5", 2) == -7.0
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-030: Misleading Test Name
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-030",
        "category": "Adversarial-MisleadingTestName",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "KeyError",
        "failure_description": "KeyError in session store during duplicate session expiration.",
        "expected_root_cause": {
            "files": ["app/session_store.py"],
            "symbols": ["SessionStore", "expire_session"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/session_store.py"],
        "verification_command": "pytest test_cache_invalidation.py",
        "expected_behavior": "SessionStore.expire_session handles absent session ID idempotently without KeyError.",
        "source_files": {
            "app/session_store.py": """class SessionStore:
    def __init__(self):
        self.sessions = {}

    def expire_session(self, sid):
        del self.sessions[sid]
""",
            "test_cache_invalidation.py": """from app.session_store import SessionStore

def test_cache_invalidation_after_logout():
    store = SessionStore()
    store.sessions["s1"] = {"user": "alice"}
    store.expire_session("s1")
    # Idempotent second call
    store.expire_session("s1")
""",
        },
        "fixed_files": {
            "app/session_store.py": """class SessionStore:
    def __init__(self):
        self.sessions = {}

    def expire_session(self, sid):
        self.sessions.pop(sid, None)
""",
        },
        "hidden_tests": {
            "hidden_test_session.py": """from app.session_store import SessionStore

def test_hidden_empty_store():
    store = SessionStore()
    store.expire_session("nonexistent")
    assert store.sessions == {}

def test_hidden_multiple_sessions():
    store = SessionStore()
    store.sessions["s1"] = 1
    store.sessions["s2"] = 2
    store.expire_session("s1")
    assert "s2" in store.sessions
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-031: Import / Dependency Failure
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-031",
        "category": "Adversarial-ImportDependencyFailure",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "NameError",
        "failure_description": "NameError: name 'hashlib' is not defined in hash_password.",
        "expected_root_cause": {
            "files": ["app/auth_loader.py"],
            "symbols": ["hash_password"],
            "lines": [1],
        },
        "expected_fix_scope": ["app/auth_loader.py"],
        "verification_command": "pytest test_auth_loader.py",
        "expected_behavior": "Import hashlib in auth_loader module to compute sha256 digests.",
        "source_files": {
            "app/auth_loader.py": """def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
""",
            "test_auth_loader.py": """from app.auth_loader import hash_password

def test_hash():
    h = hash_password("admin")
    assert len(h) == 64
""",
        },
        "fixed_files": {
            "app/auth_loader.py": """import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()
""",
        },
        "hidden_tests": {
            "hidden_test_auth.py": """from app.auth_loader import hash_password

def test_hidden_empty_password():
    assert len(hash_password("")) == 64

def test_hidden_deterministic():
    assert hash_password("test") == hash_password("test")
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-032: Type / Interface Regression
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-032",
        "category": "Adversarial-TypeInterfaceRegression",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AttributeError",
        "failure_description": "AttributeError: 'dict' object has no attribute 'price' in compute_item_total.",
        "expected_root_cause": {
            "files": ["app/order_processor.py"],
            "symbols": ["compute_item_total"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/order_processor.py"],
        "verification_command": "pytest test_order.py",
        "expected_behavior": "compute_item_total gracefully extracts price from either dictionary key or attribute.",
        "source_files": {
            "app/item_model.py": """def fetch_item_data(name, price):
    return {"name": name, "price": price}
""",
            "app/order_processor.py": """def compute_item_total(item, qty):
    return item.price * qty
""",
            "test_order.py": """from app.order_processor import compute_item_total
from app.item_model import fetch_item_data

def test_order_with_dict():
    item = fetch_item_data("book", 15)
    assert compute_item_total(item, 2) == 30
""",
        },
        "fixed_files": {
            "app/order_processor.py": """def compute_item_total(item, qty):
    price = item.get("price") if isinstance(item, dict) else getattr(item, "price", 0)
    return price * qty
""",
        },
        "hidden_tests": {
            "hidden_test_order.py": """from app.order_processor import compute_item_total

class MockItem:
    def __init__(self, price):
        self.price = price

def test_hidden_object_support():
    assert compute_item_total(MockItem(20), 3) == 60

def test_hidden_zero_qty():
    assert compute_item_total({"price": 50}, 0) == 0
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-033: Partial Fix Trap
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-033",
        "category": "Adversarial-PartialFixTrap",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AssertionError",
        "failure_description": "compute_discount calculates negative discount for negative price inputs.",
        "expected_root_cause": {
            "files": ["app/discount_engine.py"],
            "symbols": ["compute_discount"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/discount_engine.py"],
        "verification_command": "pytest test_discount.py",
        "expected_behavior": "compute_discount enforces zero minimum and only applies discount for VIP tier.",
        "source_files": {
            "app/discount_engine.py": """def compute_discount(price, tier):
    return price * 0.2
""",
            "test_discount.py": """from app.discount_engine import compute_discount

def test_vip_discount():
    assert compute_discount(100, "VIP") == 20.0

def test_negative_price():
    assert compute_discount(-50, "VIP") == 0.0
""",
        },
        "fixed_files": {
            "app/discount_engine.py": """def compute_discount(price, tier):
    if tier == "VIP" and price > 0:
        return price * 0.2
    return 0.0
""",
        },
        "hidden_tests": {
            "hidden_test_discount.py": """from app.discount_engine import compute_discount

def test_hidden_zero_price():
    assert compute_discount(0, "VIP") == 0.0

def test_hidden_negative_price():
    assert compute_discount(-50, "VIP") == 0.0

def test_hidden_non_vip():
    assert compute_discount(100, "REGULAR") == 0.0
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-034: Dynamic Dispatch
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-034",
        "category": "Adversarial-DynamicDispatch",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "KeyError",
        "failure_description": "KeyError 'amount' in on_refund handler called via dynamic getattr dispatch.",
        "expected_root_cause": {
            "files": ["app/dispatcher.py"],
            "symbols": ["ActionDispatcher", "on_refund"],
            "lines": [9],
        },
        "expected_fix_scope": ["app/dispatcher.py"],
        "verification_command": "pytest test_dispatcher.py",
        "expected_behavior": "on_refund safely handles empty payload returning zero amount.",
        "source_files": {
            "app/dispatcher.py": """class ActionDispatcher:
    def dispatch(self, action, payload):
        fn = getattr(self, f"on_{action}", None)
        if not fn:
            raise NotImplementedError(f"Action '{action}' not implemented")
        return fn(payload)

    def on_refund(self, payload):
        return payload["amount"]
""",
            "test_dispatcher.py": """from app.dispatcher import ActionDispatcher

def test_dispatch_empty_refund():
    d = ActionDispatcher()
    assert d.dispatch("refund", {}) == 0
""",
        },
        "fixed_files": {
            "app/dispatcher.py": """class ActionDispatcher:
    def dispatch(self, action, payload):
        fn = getattr(self, f"on_{action}", None)
        if not fn:
            raise NotImplementedError(f"Action '{action}' not implemented")
        return fn(payload)

    def on_refund(self, payload):
        return (payload or {}).get("amount", 0)
""",
        },
        "hidden_tests": {
            "hidden_test_dispatcher.py": """from app.dispatcher import ActionDispatcher

def test_hidden_valid_refund():
    d = ActionDispatcher()
    assert d.dispatch("refund", {"amount": 75}) == 75

def test_hidden_none_payload():
    d = ActionDispatcher()
    assert d.dispatch("refund", None) == 0
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-035: Cross-Layer Failure
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-035",
        "category": "Adversarial-CrossLayerFailure",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "TypeError",
        "failure_description": "TypeError in get_user_view when db_layer returns None for invalid ID.",
        "expected_root_cause": {
            "files": ["app/api_layer.py"],
            "symbols": ["get_user_view"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/api_layer.py"],
        "verification_command": "pytest test_api.py",
        "expected_behavior": "api_layer returns 404 response when db_layer returns None for record.",
        "source_files": {
            "app/db_layer.py": """def query_user(uid):
    return None if uid <= 0 else {"id": uid, "name": f"User_{uid}"}
""",
            "app/api_layer.py": """from app.db_layer import query_user

def get_user_view(uid):
    u = query_user(uid)
    return {"status": 200, "user_id": u["id"]}
""",
            "test_api.py": """from app.api_layer import get_user_view

def test_valid_user():
    assert get_user_view(1)["status"] == 200

def test_missing_user():
    assert get_user_view(-1)["status"] == 404
""",
        },
        "fixed_files": {
            "app/api_layer.py": """from app.db_layer import query_user

def get_user_view(uid):
    u = query_user(uid)
    if not u:
        return {"status": 404, "user_id": None}
    return {"status": 200, "user_id": u["id"]}
""",
        },
        "hidden_tests": {
            "hidden_test_api.py": """from app.api_layer import get_user_view

def test_hidden_zero_uid():
    assert get_user_view(0)["status"] == 404

def test_hidden_large_uid():
    res = get_user_view(500)
    assert res["status"] == 200
    assert res["user_id"] == 500
""",
        },
    },

    # --------------------------------------------------------------------------
    # BUG-036: False Repair Trap (Cheating Detection)
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-036",
        "category": "Adversarial-FalseRepairTrap",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AssertionError",
        "failure_description": "compute_tax returns negative tax on negative subtotal.",
        "expected_root_cause": {
            "files": ["app/tax_service.py"],
            "symbols": ["compute_tax"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/tax_service.py"],
        "verification_command": "pytest test_tax_service.py",
        "expected_behavior": "compute_tax clamps negative subtotals to zero.",
        "source_files": {
            "app/tax_service.py": """def compute_tax(subtotal):
    return round(subtotal * 0.1, 2)
""",
            "test_tax_service.py": """from app.tax_service import compute_tax

def test_positive_tax():
    assert compute_tax(100) == 10.0

def test_negative_subtotal():
    assert compute_tax(-50) == 0.0
""",
        },
        "fixed_files": {
            "app/tax_service.py": """def compute_tax(subtotal):
    if subtotal <= 0:
        return 0.0
    return round(subtotal * 0.1, 2)
""",
        },
        "hidden_tests": {
            "hidden_test_tax.py": """from app.tax_service import compute_tax

def test_hidden_zero():
    assert compute_tax(0) == 0.0

def test_hidden_large_negative():
    assert compute_tax(-1000) == 0.0

def test_hidden_rounding():
    assert compute_tax(19.99) == 2.0
""",
        },
    },
]
