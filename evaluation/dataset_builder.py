"""Devaura Phase 8 Benchmark Dataset Builder.

Generates 25 deterministic, reproducible benchmark cases spanning 8 failure categories.
Uses difflib to compute golden unified diffs with exact standard patch syntax.
"""

import difflib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# Ensure repo root is on sys.path when invoked directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DATASET_ROOT = Path(__file__).parent / "dataset"
BUGS_DIR = DATASET_ROOT / "bugs"

BUGS: List[Dict[str, Any]] = [
    # --------------------------------------------------------------------------
    # Category A: Exceptions
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-001",
        "category": "A-Exceptions",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "AttributeError",
        "failure_description": "AttributeError: 'NoneType' object has no attribute 'get' in user processor.",
        "expected_root_cause": {
            "files": ["app/processor.py"],
            "symbols": ["process_user_profile"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/processor.py"],
        "verification_command": "pytest test_processor.py",
        "expected_behavior": "Defensively handle None user profile by returning default metadata.",
        "source_files": {
            "app/processor.py": """def process_user_profile(user_dict):
    if user_dict is None:
        user_dict = {}
    profile = user_dict.get("profile")
    return profile.get("username", "anonymous")
""",
            "test_processor.py": """from app.processor import process_user_profile

def test_process_valid_user():
    assert process_user_profile({"profile": {"username": "alice"}}) == "alice"

def test_process_none_profile():
    assert process_user_profile({"profile": None}) == "anonymous"

def test_process_missing_profile():
    assert process_user_profile({}) == "anonymous"
""",
        },
        "fixed_files": {
            "app/processor.py": """def process_user_profile(user_dict):
    if user_dict is None:
        user_dict = {}
    profile = user_dict.get("profile")
    return (profile or {}).get("username", "anonymous")
""",
        },
    },
    {
        "bug_id": "BUG-002",
        "category": "A-Exceptions",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "KeyError",
        "failure_description": "KeyError: 'status' in webhook payload event router.",
        "expected_root_cause": {
            "files": ["app/webhook.py"],
            "symbols": ["route_webhook_event"],
            "lines": [4],
        },
        "expected_fix_scope": ["app/webhook.py"],
        "verification_command": "pytest test_webhook.py",
        "expected_behavior": "Safely read status from payload without raising KeyError on partial events.",
        "source_files": {
            "app/webhook.py": """def route_webhook_event(payload):
    event_type = payload.get("event", "unknown")
    status = payload["status"]
    return f"{event_type}:{status}"
""",
            "test_webhook.py": """from app.webhook import route_webhook_event

def test_route_full_payload():
    assert route_webhook_event({"event": "payment", "status": "completed"}) == "payment:completed"

def test_route_missing_status():
    assert route_webhook_event({"event": "ping"}) == "ping:pending"
""",
        },
        "fixed_files": {
            "app/webhook.py": """def route_webhook_event(payload):
    event_type = payload.get("event", "unknown")
    status = payload.get("status", "pending")
    return f"{event_type}:{status}"
""",
        },
    },
    {
        "bug_id": "BUG-003",
        "category": "A-Exceptions",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "TypeError",
        "failure_description": "TypeError: unsupported operand type(s) for +: 'int' and 'str' in invoice total.",
        "expected_root_cause": {
            "files": ["app/invoice.py"],
            "symbols": ["calculate_invoice_total"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/invoice.py"],
        "verification_command": "pytest test_invoice.py",
        "expected_behavior": "Convert line item amounts to numeric float before sum aggregation.",
        "source_files": {
            "app/invoice.py": """def calculate_invoice_total(items):
    total = 0.0
    for item in items:
        amount = item.get("amount", 0)
        total += amount
    return round(total, 2)
""",
            "test_invoice.py": """from app.invoice import calculate_invoice_total

def test_numeric_items():
    assert calculate_invoice_total([{"amount": 10.5}, {"amount": 20.0}]) == 30.5

def test_string_item_coercion():
    assert calculate_invoice_total([{"amount": "15.50"}, {"amount": 4.5}]) == 20.0
""",
        },
        "fixed_files": {
            "app/invoice.py": """def calculate_invoice_total(items):
    total = 0.0
    for item in items:
        amount = item.get("amount", 0)
        total += float(amount)
    return round(total, 2)
""",
        },
    },
    {
        "bug_id": "BUG-004",
        "category": "A-Exceptions",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "IndexError",
        "failure_description": "IndexError: list index out of range in sliding window aggregator.",
        "expected_root_cause": {
            "files": ["app/window.py"],
            "symbols": ["get_window_boundary"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/window.py"],
        "verification_command": "pytest test_window.py",
        "expected_behavior": "Safely return (None, None) when items array is empty.",
        "source_files": {
            "app/window.py": """def get_window_boundary(items):
    first_elem = items[0]
    last_elem = items[-1]
    return (first_elem, last_elem)
""",
            "test_window.py": """from app.window import get_window_boundary

def test_non_empty_window():
    assert get_window_boundary([10, 20, 30]) == (10, 30)

def test_empty_window():
    assert get_window_boundary([]) == (None, None)
""",
        },
        "fixed_files": {
            "app/window.py": """def get_window_boundary(items):
    if not items:
        return (None, None)
    first_elem = items[0]
    last_elem = items[-1]
    return (first_elem, last_elem)
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category B: Failed Tests
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-005",
        "category": "B-Failed Tests",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "AssertionError",
        "failure_description": "calculate_discount returns decimal proportion instead of dollar discount amount.",
        "expected_root_cause": {
            "files": ["app/discounts.py"],
            "symbols": ["apply_tier_discount"],
            "lines": [4],
        },
        "expected_fix_scope": ["app/discounts.py"],
        "verification_command": "pytest test_discounts.py",
        "expected_behavior": "Return price * (1.0 - rate).",
        "source_files": {
            "app/discounts.py": """def apply_tier_discount(price, tier):
    rates = {"gold": 0.20, "silver": 0.10, "bronze": 0.05}
    rate = rates.get(tier, 0.0)
    return price * rate
""",
            "test_discounts.py": """from app.discounts import apply_tier_discount

def test_gold_discount():
    assert apply_tier_discount(100.0, "gold") == 80.0

def test_unknown_tier():
    assert apply_tier_discount(100.0, "guest") == 100.0
""",
        },
        "fixed_files": {
            "app/discounts.py": """def apply_tier_discount(price, tier):
    rates = {"gold": 0.20, "silver": 0.10, "bronze": 0.05}
    rate = rates.get(tier, 0.0)
    return price * (1.0 - rate)
""",
        },
    },
    {
        "bug_id": "BUG-006",
        "category": "B-Failed Tests",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "AssertionError",
        "failure_description": "Inverted condition in rate limiter threshold check.",
        "expected_root_cause": {
            "files": ["app/ratelimit.py"],
            "symbols": ["is_rate_limited"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/ratelimit.py"],
        "verification_command": "pytest test_ratelimit.py",
        "expected_behavior": "Return True when current_requests >= max_allowed.",
        "source_files": {
            "app/ratelimit.py": """def is_rate_limited(current_requests, max_allowed):
    return current_requests < max_allowed
""",
            "test_ratelimit.py": """from app.ratelimit import is_rate_limited

def test_under_limit():
    assert is_rate_limited(5, 10) is False

def test_over_limit():
    assert is_rate_limited(12, 10) is True

def test_at_limit():
    assert is_rate_limited(10, 10) is True
""",
        },
        "fixed_files": {
            "app/ratelimit.py": """def is_rate_limited(current_requests, max_allowed):
    return current_requests >= max_allowed
""",
        },
    },
    {
        "bug_id": "BUG-007",
        "category": "B-Failed Tests",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "ZeroDivisionError",
        "failure_description": "ZeroDivisionError in unit price calculation when quantity is zero.",
        "expected_root_cause": {
            "files": ["app/pricing.py"],
            "symbols": ["unit_price"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/pricing.py"],
        "verification_command": "pytest test_pricing.py",
        "expected_behavior": "Return 0.0 when quantity is zero.",
        "source_files": {
            "app/pricing.py": """def unit_price(total_cost, quantity):
    return round(total_cost / quantity, 2)
""",
            "test_pricing.py": """from app.pricing import unit_price

def test_positive_quantity():
    assert unit_price(100.0, 4) == 25.0

def test_zero_quantity():
    assert unit_price(100.0, 0) == 0.0
""",
        },
        "fixed_files": {
            "app/pricing.py": """def unit_price(total_cost, quantity):
    if quantity == 0:
        return 0.0
    return round(total_cost / quantity, 2)
""",
        },
    },
    {
        "bug_id": "BUG-008",
        "category": "B-Failed Tests",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "AssertionError",
        "failure_description": "Boundary condition bug in leap year century calculation.",
        "expected_root_cause": {
            "files": ["app/calendar_util.py"],
            "symbols": ["is_leap_year"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/calendar_util.py"],
        "verification_command": "pytest test_calendar_util.py",
        "expected_behavior": "A year divisible by 100 is only leap if divisible by 400.",
        "source_files": {
            "app/calendar_util.py": """def is_leap_year(year):
    if year % 100 == 0:
        return True
    return year % 4 == 0
""",
            "test_calendar_util.py": """from app.calendar_util import is_leap_year

def test_standard_leap_year():
    assert is_leap_year(2024) is True

def test_century_not_divisible_by_400():
    assert is_leap_year(1900) is False

def test_century_divisible_by_400():
    assert is_leap_year(2000) is True
""",
        },
        "fixed_files": {
            "app/calendar_util.py": """def is_leap_year(year):
    if year % 400 == 0:
        return True
    if year % 100 == 0:
        return False
    return year % 4 == 0
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category C: Import / Dependency Failures
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-009",
        "category": "C-Import / Dependency Failures",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "NameError",
        "failure_description": "NameError: name 'hashlib' is not defined in token hasher.",
        "expected_root_cause": {
            "files": ["app/security.py"],
            "symbols": ["hash_auth_token"],
            "lines": [1],
        },
        "expected_fix_scope": ["app/security.py"],
        "verification_command": "pytest test_security.py",
        "expected_behavior": "Import hashlib module at top of security.py.",
        "source_files": {
            "app/security.py": """def hash_auth_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
""",
            "test_security.py": """from app.security import hash_auth_token

def test_hash_token():
    res = hash_auth_token("secret123")
    assert len(res) == 64
""",
        },
        "fixed_files": {
            "app/security.py": """import hashlib

def hash_auth_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
""",
        },
    },
    {
        "bug_id": "BUG-010",
        "category": "C-Import / Dependency Failures",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "ImportError",
        "failure_description": "ImportError: cannot import name 'format_currency' from 'app.helpers'.",
        "expected_root_cause": {
            "files": ["app/display.py"],
            "symbols": ["render_balance"],
            "lines": [1],
        },
        "expected_fix_scope": ["app/display.py"],
        "verification_command": "pytest test_display.py",
        "expected_behavior": "Import renamed helper format_price as format_currency.",
        "source_files": {
            "app/helpers.py": """def format_price(amount):
    return f"${amount:,.2f}"
""",
            "app/display.py": """from app.helpers import format_currency

def render_balance(account_name, balance):
    return f"{account_name}: {format_currency(balance)}"
""",
            "test_display.py": """from app.display import render_balance

def test_render_balance():
    assert render_balance("Checking", 1500) == "Checking: $1,500.00"
""",
        },
        "fixed_files": {
            "app/display.py": """from app.helpers import format_price as format_currency

def render_balance(account_name, balance):
    return f"{account_name}: {format_currency(balance)}"
""",
        },
    },
    {
        "bug_id": "BUG-011",
        "category": "C-Import / Dependency Failures",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "ModuleNotFoundError",
        "failure_description": "ModuleNotFoundError: No module named 'app.legacy_db'.",
        "expected_root_cause": {
            "files": ["app/repository.py"],
            "symbols": ["get_record"],
            "lines": [1],
        },
        "expected_fix_scope": ["app/repository.py"],
        "verification_command": "pytest test_repository.py",
        "expected_behavior": "Update import path from app.legacy_db to app.database.",
        "source_files": {
            "app/database.py": """DATABASE = {"u1": "Alice", "u2": "Bob"}

def query_record(record_id):
    return DATABASE.get(record_id)
""",
            "app/repository.py": """from app.legacy_db import query_record

def get_record(record_id):
    return query_record(record_id)
""",
            "test_repository.py": """from app.repository import get_record

def test_get_existing():
    assert get_record("u1") == "Alice"
""",
        },
        "fixed_files": {
            "app/repository.py": """from app.database import query_record

def get_record(record_id):
    return query_record(record_id)
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category D: Logic Bugs
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-012",
        "category": "D-Logic Bugs",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "AssertionError",
        "failure_description": "Tax exempt check inverts non-US exemption rule.",
        "expected_root_cause": {
            "files": ["app/taxes.py"],
            "symbols": ["calculate_sales_tax"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/taxes.py"],
        "verification_command": "pytest test_taxes.py",
        "expected_behavior": "Apply 0% tax when country is EXEMPT_ZONE.",
        "source_files": {
            "app/taxes.py": """def calculate_sales_tax(subtotal, country):
    if country == "EXEMPT_ZONE":
        tax_rate = 0.20
    else:
        tax_rate = 0.0
    return round(subtotal * tax_rate, 2)
""",
            "test_taxes.py": """from app.taxes import calculate_sales_tax

def test_exempt_zone():
    assert calculate_sales_tax(100.0, "EXEMPT_ZONE") == 0.0

def test_standard_zone():
    assert calculate_sales_tax(100.0, "US") == 20.0
""",
        },
        "fixed_files": {
            "app/taxes.py": """def calculate_sales_tax(subtotal, country):
    if country != "EXEMPT_ZONE":
        tax_rate = 0.20
    else:
        tax_rate = 0.0
    return round(subtotal * tax_rate, 2)
""",
        },
    },
    {
        "bug_id": "BUG-013",
        "category": "D-Logic Bugs",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "AssertionError",
        "failure_description": "Permissions logic rejects superuser role.",
        "expected_root_cause": {
            "files": ["app/auth_policy.py"],
            "symbols": ["has_access"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/auth_policy.py"],
        "verification_command": "pytest test_auth_policy.py",
        "expected_behavior": "Allow both 'admin' and 'superuser' roles to pass access check.",
        "source_files": {
            "app/auth_policy.py": """def has_access(user_role):
    return user_role == "admin"
""",
            "test_auth_policy.py": """from app.auth_policy import has_access

def test_admin_access():
    assert has_access("admin") is True

def test_superuser_access():
    assert has_access("superuser") is True

def test_guest_access():
    assert has_access("guest") is False
""",
        },
        "fixed_files": {
            "app/auth_policy.py": """def has_access(user_role):
    return user_role in {"admin", "superuser"}
""",
        },
    },
    {
        "bug_id": "BUG-014",
        "category": "D-Logic Bugs",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "AssertionError",
        "failure_description": "Off-by-one in paginate_results omitting last element.",
        "expected_root_cause": {
            "files": ["app/pagination.py"],
            "symbols": ["paginate_items"],
            "lines": [3],
        },
        "expected_fix_scope": ["app/pagination.py"],
        "verification_command": "pytest test_pagination.py",
        "expected_behavior": "Correctly compute end index as start + page_size.",
        "source_files": {
            "app/pagination.py": """def paginate_items(items, page, page_size):
    start = (page - 1) * page_size
    end = start + page_size - 1
    return items[start:end]
""",
            "test_pagination.py": """from app.pagination import paginate_items

def test_page_size_three():
    data = [1, 2, 3, 4, 5, 6]
    assert paginate_items(data, page=1, page_size=3) == [1, 2, 3]
    assert paginate_items(data, page=2, page_size=3) == [4, 5, 6]
""",
        },
        "fixed_files": {
            "app/pagination.py": """def paginate_items(items, page, page_size):
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end]
""",
        },
    },
    {
        "bug_id": "BUG-015",
        "category": "D-Logic Bugs",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "AssertionError",
        "failure_description": "Invalid state machine transition permitted from CANCELLED to COMPLETED.",
        "expected_root_cause": {
            "files": ["app/order_fsm.py"],
            "symbols": ["can_transition"],
            "lines": [4],
        },
        "expected_fix_scope": ["app/order_fsm.py"],
        "verification_command": "pytest test_order_fsm.py",
        "expected_behavior": "Disallow transitions out of terminal CANCELLED state.",
        "source_files": {
            "app/order_fsm.py": """ALLOWED_TRANSITIONS = {
    "CREATED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["COMPLETED", "CANCELLED"],
    "CANCELLED": ["COMPLETED"],
    "COMPLETED": []
}

def can_transition(current, target):
    return target in ALLOWED_TRANSITIONS.get(current, [])
""",
            "test_order_fsm.py": """from app.order_fsm import can_transition

def test_valid_transition():
    assert can_transition("CREATED", "PROCESSING") is True

def test_terminal_cancelled():
    assert can_transition("CANCELLED", "COMPLETED") is False
""",
        },
        "fixed_files": {
            "app/order_fsm.py": """ALLOWED_TRANSITIONS = {
    "CREATED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["COMPLETED", "CANCELLED"],
    "CANCELLED": [],
    "COMPLETED": []
}

def can_transition(current, target):
    return target in ALLOWED_TRANSITIONS.get(current, [])
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category E: Regression Bugs
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-016",
        "category": "E-Regression Bugs",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "AssertionError",
        "failure_description": "Shared default mutable dictionary pollutes subsequent config calls.",
        "expected_root_cause": {
            "files": ["app/config_loader.py"],
            "symbols": ["build_config"],
            "lines": [1],
        },
        "expected_fix_scope": ["app/config_loader.py"],
        "verification_command": "pytest test_config_loader.py",
        "expected_behavior": "Use None default and instantiate new dict per invocation.",
        "source_files": {
            "app/config_loader.py": """def build_config(options={}):
    options["loaded"] = True
    return options
""",
            "test_config_loader.py": """from app.config_loader import build_config

def test_isolated_configs():
    c1 = build_config()
    c1["env"] = "dev"
    c2 = build_config()
    assert "env" not in c2
""",
        },
        "fixed_files": {
            "app/config_loader.py": """def build_config(options=None):
    if options is None:
        options = {}
    options["loaded"] = True
    return options
""",
        },
    },
    {
        "bug_id": "BUG-017",
        "category": "E-Regression Bugs",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "TypeError",
        "failure_description": "Function signature refactor broke callers expecting optional parameter.",
        "expected_root_cause": {
            "files": ["app/formatter.py"],
            "symbols": ["format_header"],
            "lines": [1],
        },
        "expected_fix_scope": ["app/formatter.py"],
        "verification_command": "pytest test_formatter.py",
        "expected_behavior": "Restore default prefix='' parameter for backward compatibility.",
        "source_files": {
            "app/formatter.py": """def format_header(title, prefix):
    return f"{prefix}{title}"
""",
            "test_formatter.py": """from app.formatter import format_header

def test_with_prefix():
    assert format_header("Summary", ">>> ") == ">>> Summary"

def test_without_prefix_regression():
    assert format_header("Summary") == "Summary"
""",
        },
        "fixed_files": {
            "app/formatter.py": """def format_header(title, prefix=""):
    return f"{prefix}{title}"
""",
        },
    },
    {
        "bug_id": "BUG-018",
        "category": "E-Regression Bugs",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "AttributeError",
        "failure_description": "Refactor changed list return to dictionary, breaking caller iterating on list.",
        "expected_root_cause": {
            "files": ["app/list_provider.py"],
            "symbols": ["get_active_tags"],
            "lines": [4],
        },
        "expected_fix_scope": ["app/list_provider.py"],
        "verification_command": "pytest test_list_provider.py",
        "expected_behavior": "Return list of active tags matching caller interface contract.",
        "source_files": {
            "app/list_provider.py": """TAG_DATA = {"v1": True, "v2": False, "v3": True}

def get_active_tags():
    return {k: v for k, v in TAG_DATA.items() if v}
""",
            "test_list_provider.py": """from app.list_provider import get_active_tags

def test_returns_list_of_tags():
    tags = get_active_tags()
    assert isinstance(tags, list)
    assert "v1" in tags
    assert "v2" not in tags
""",
        },
        "fixed_files": {
            "app/list_provider.py": """TAG_DATA = {"v1": True, "v2": False, "v3": True}

def get_active_tags():
    return [k for k, v in TAG_DATA.items() if v]
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category F: Multi-file Bugs
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-019",
        "category": "F-Multi-file Bugs",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "KeyError",
        "failure_description": "Caller in client.py expects 'id' but serializer in serializer.py emits 'user_id'.",
        "expected_root_cause": {
            "files": ["app/serializer.py"],
            "symbols": ["serialize_user"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/serializer.py"],
        "verification_command": "pytest test_client.py",
        "expected_behavior": "Include 'id' key alongside user_id for backward compatibility with client.py.",
        "source_files": {
            "app/serializer.py": """def serialize_user(raw_user):
    return {
        "user_id": raw_user["uid"],
        "name": raw_user["name"],
    }
""",
            "app/client.py": """from app.serializer import serialize_user

def get_formatted_user(raw_user):
    s = serialize_user(raw_user)
    return f"User #{s['id']}: {s['name']}"
""",
            "test_client.py": """from app.client import get_formatted_user

def test_formatted_user():
    res = get_formatted_user({"uid": 42, "name": "Bob"})
    assert res == "User #42: Bob"
""",
        },
        "fixed_files": {
            "app/serializer.py": """def serialize_user(raw_user):
    return {
        "id": raw_user["uid"],
        "user_id": raw_user["uid"],
        "name": raw_user["name"],
    }
""",
        },
    },
    {
        "bug_id": "BUG-020",
        "category": "F-Multi-file Bugs",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AssertionError",
        "failure_description": "Config timeout value in settings.py not respected in http_service.py default timeout.",
        "expected_root_cause": {
            "files": ["app/http_service.py"],
            "symbols": ["get_request_timeout"],
            "lines": [4],
        },
        "expected_fix_scope": ["app/http_service.py"],
        "verification_command": "pytest test_http_service.py",
        "expected_behavior": "Import DEFAULT_TIMEOUT from app.settings and use as fallback.",
        "source_files": {
            "app/settings.py": """DEFAULT_TIMEOUT = 30
""",
            "app/http_service.py": """def get_request_timeout(override=None):
    if override is not None:
        return override
    return 5
""",
            "test_http_service.py": """from app.http_service import get_request_timeout

def test_default_timeout():
    assert get_request_timeout() == 30

def test_override_timeout():
    assert get_request_timeout(10) == 10
""",
        },
        "fixed_files": {
            "app/http_service.py": """from app.settings import DEFAULT_TIMEOUT

def get_request_timeout(override=None):
    if override is not None:
        return override
    return DEFAULT_TIMEOUT
""",
        },
    },
    {
        "bug_id": "BUG-021",
        "category": "F-Multi-file Bugs",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "KeyError",
        "failure_description": "Model field in models.py updated to 'created_timestamp' but repository query accesses 'created_at'.",
        "expected_root_cause": {
            "files": ["app/repo.py"],
            "symbols": ["get_record_timestamp"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/repo.py"],
        "verification_command": "pytest test_repo.py",
        "expected_behavior": "Query 'created_timestamp' or fallback to 'created_at'.",
        "source_files": {
            "app/models.py": """def make_record(rec_id, ts):
    return {"id": rec_id, "created_timestamp": ts}
""",
            "app/repo.py": """def get_record_timestamp(record):
    return record["created_at"]
""",
            "test_repo.py": """from app.models import make_record
from app.repo import get_record_timestamp

def test_get_timestamp():
    r = make_record("r1", 1700000000)
    assert get_record_timestamp(r) == 1700000000
""",
        },
        "fixed_files": {
            "app/repo.py": """def get_record_timestamp(record):
    return record.get("created_timestamp", record.get("created_at"))
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category G: Type / Static Analysis Failures
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-022",
        "category": "G-Type / Static Analysis Failures",
        "language": "python",
        "difficulty": "medium",
        "failure_type": "TypeError",
        "failure_description": "Passing None to non-optional string join parameter raises TypeError.",
        "expected_root_cause": {
            "files": ["app/string_utils.py"],
            "symbols": ["join_tokens"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/string_utils.py"],
        "verification_command": "pytest test_string_utils.py",
        "expected_behavior": "Filter out None values before joining tokens.",
        "source_files": {
            "app/string_utils.py": """def join_tokens(tokens):
    return " ".join(tokens)
""",
            "test_string_utils.py": """from app.string_utils import join_tokens

def test_clean_tokens():
    assert join_tokens(["hello", "world"]) == "hello world"

def test_tokens_with_none():
    assert join_tokens(["hello", None, "world"]) == "hello world"
""",
        },
        "fixed_files": {
            "app/string_utils.py": """def join_tokens(tokens):
    return " ".join(str(t) for t in tokens if t is not None)
""",
        },
    },
    {
        "bug_id": "BUG-023",
        "category": "G-Type / Static Analysis Failures",
        "language": "python",
        "difficulty": "easy",
        "failure_type": "NameError",
        "failure_description": "Undefined variable 'err_log' referenced in exception handler.",
        "expected_root_cause": {
            "files": ["app/logger_handler.py"],
            "symbols": ["handle_error"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/logger_handler.py"],
        "verification_command": "pytest test_logger_handler.py",
        "expected_behavior": "Reference defined variable 'err' in exception block.",
        "source_files": {
            "app/logger_handler.py": """def handle_error(action_fn):
    try:
        return action_fn()
    except Exception as err:
        return f"Error: {err_log}"
""",
            "test_logger_handler.py": """from app.logger_handler import handle_error

def test_successful_action():
    assert handle_error(lambda: "OK") == "OK"

def test_failed_action():
    assert handle_error(lambda: 1 / 0) == "Error: division by zero"
""",
        },
        "fixed_files": {
            "app/logger_handler.py": """def handle_error(action_fn):
    try:
        return action_fn()
    except Exception as err:
        return f"Error: {err}"
""",
        },
    },

    # --------------------------------------------------------------------------
    # Category H: Test/Source Relationship Bugs
    # --------------------------------------------------------------------------
    {
        "bug_id": "BUG-024",
        "category": "H-Test/Source Relationship Bugs",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AssertionError",
        "failure_description": "Failing test in test_facade.py tests OrderFacade, but root cause is in InventoryEngine.reserve_stock.",
        "expected_root_cause": {
            "files": ["app/inventory.py"],
            "symbols": ["reserve_stock"],
            "lines": [5],
        },
        "expected_fix_scope": ["app/inventory.py"],
        "verification_command": "pytest test_facade.py",
        "expected_behavior": "Update inventory reservation logic to decrement available count accurately.",
        "source_files": {
            "app/inventory.py": """STOCK = {"item_1": 10}

def reserve_stock(item_id, count):
    current = STOCK.get(item_id, 0)
    STOCK[item_id] = current + count
    return True
""",
            "app/facade.py": """from app.inventory import reserve_stock, STOCK

class OrderFacade:
    def place_order(self, item_id, count):
        reserve_stock(item_id, count)
        return STOCK.get(item_id)
""",
            "test_facade.py": """from app.facade import OrderFacade

def test_order_facade_placement():
    facade = OrderFacade()
    rem = facade.place_order("item_1", 2)
    assert rem == 8
""",
        },
        "fixed_files": {
            "app/inventory.py": """STOCK = {"item_1": 10}

def reserve_stock(item_id, count):
    current = STOCK.get(item_id, 0)
    STOCK[item_id] = current - count
    return True
""",
        },
    },
    {
        "bug_id": "BUG-025",
        "category": "H-Test/Source Relationship Bugs",
        "language": "python",
        "difficulty": "hard",
        "failure_type": "AssertionError",
        "failure_description": "Test fixture helper creates UTC timestamp with local offset skew.",
        "expected_root_cause": {
            "files": ["app/time_helper.py"],
            "symbols": ["normalize_utc_timestamp"],
            "lines": [2],
        },
        "expected_fix_scope": ["app/time_helper.py"],
        "verification_command": "pytest test_timestamp.py",
        "expected_behavior": "Normalize timestamp to UTC timezone without adding local offset.",
        "source_files": {
            "app/time_helper.py": """def normalize_utc_timestamp(epoch_seconds, offset_hours=0):
    return epoch_seconds + (offset_hours * 3600)
""",
            "test_timestamp.py": """from app.time_helper import normalize_utc_timestamp

def test_zero_offset():
    assert normalize_utc_timestamp(1700000000, 0) == 1700000000

def test_normalize_strips_offset():
    assert normalize_utc_timestamp(1700000000, 5) == 1700000000
""",
        },
        "fixed_files": {
            "app/time_helper.py": """def normalize_utc_timestamp(epoch_seconds, offset_hours=0):
    return epoch_seconds
""",
        },
    },
]

from evaluation.adversarial_bugs import ADVERSARIAL_BUGS
from evaluation.hidden_tests_map import HIDDEN_TESTS_FOR_BASELINE

ALL_BUGS: List[Dict[str, Any]] = BUGS + ADVERSARIAL_BUGS


def build_dataset():
    """Generates the directory tree and manifest for the benchmark dataset."""
    DATASET_ROOT.mkdir(parents=True, exist_ok=True)
    BUGS_DIR.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for b in ALL_BUGS:
        bug_id = b["bug_id"]
        bug_dir = BUGS_DIR / bug_id
        broken_dir = bug_dir / "broken_code"
        broken_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write broken source files
        for rel_path, content in b["source_files"].items():
            dest = broken_dir / rel_path
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        # 2. Write hidden tests (evaluator-only independent validation)
        hidden_tests = b.get("hidden_tests") or HIDDEN_TESTS_FOR_BASELINE.get(bug_id, {})
        if hidden_tests:
            hidden_dir = bug_dir / "hidden_tests"
            hidden_dir.mkdir(parents=True, exist_ok=True)
            for rel_path, content in hidden_tests.items():
                dest = hidden_dir / rel_path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

        # 3. Compute and write golden patch using difflib
        golden_diff_lines = []
        for rel_path, fixed_content in b.get("fixed_files", {}).items():
            orig_content = b["source_files"].get(rel_path, "")
            diff = list(difflib.unified_diff(
                orig_content.splitlines(keepends=True),
                fixed_content.splitlines(keepends=True),
                fromfile=f"a/{rel_path}",
                tofile=f"b/{rel_path}",
            ))
            golden_diff_lines.extend(diff)

        patch_file = bug_dir / "golden_patch.diff"
        patch_file.write_text("".join(golden_diff_lines), encoding="utf-8")

        # 4. Write metadata.json (ground truth scoring criteria)
        metadata = {
            "bug_id": bug_id,
            "category": b["category"],
            "language": b["language"],
            "difficulty": b["difficulty"],
            "failure_type": b["failure_type"],
            "failure_description": b["failure_description"],
            "expected_root_cause": b["expected_root_cause"],
            "expected_fix_scope": b["expected_fix_scope"],
            "verification_command": b["verification_command"],
            "expected_behavior": b["expected_behavior"],
            "has_hidden_tests": bool(hidden_tests),
        }
        meta_file = bug_dir / "metadata.json"
        meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        manifest_entries.append({
            "bug_id": bug_id,
            "category": b["category"],
            "language": b["language"],
            "difficulty": b["difficulty"],
            "failure_type": b["failure_type"],
            "path": f"bugs/{bug_id}",
        })

    manifest = {
        "dataset_name": "Devaura-Benchmark-v1",
        "total_bugs": len(manifest_entries),
        "categories": sorted(list({b["category"] for b in ALL_BUGS})),
        "languages": ["python"],
        "bugs": manifest_entries,
    }
    manifest_path = DATASET_ROOT / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Generated {len(manifest_entries)} benchmark bugs in {DATASET_ROOT}")


if __name__ == "__main__":
    build_dataset()
