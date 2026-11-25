"""
Devaura Phase 11 Disposable Test Repository Setup Script.

Seeds shreyvirmani/devaura-disposable-e2e with:
1. Updated universal CI workflow (.github/workflows/ci.yml triggering on all branches)
2. base/e2e-001: Pricing service volume discount logic bug
3. base/e2e-002: Auth token validator None/metadata edge case bug
4. base/e2e-003: Multi-module order checkout & inventory reservation interface bug
5. base/e2e-004: Telemetry formatter strict ISO-8601 regression bug
6. base/e2e-005: Storage backup security/insufficient evidence defect
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
from pathlib import Path
import httpx
import dotenv

dotenv.load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("DEVAURA_GITHUB_TOKEN")
if not TOKEN:
    print("ERROR: GITHUB_TOKEN environment variable is required.")
    sys.exit(1)

OWNER = "shreyvirmani"
REPO_NAME = "devaura-disposable-e2e"
API_BASE = "https://api.github.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN.strip()}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Devaura-Phase11-Setup",
}


def setup_universal_ci_on_main(repo_dir: Path):
    """Update .github/workflows/ci.yml on main to run on all branches and PRs."""
    wf_dir = repo_dir / ".github" / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    wf_code = """name: CI

on:
  push:
    branches: [ "**" ]
  pull_request:
    branches: [ "**" ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install pytest
    - name: Run tests
      run: |
        pytest
"""
    (wf_dir / "ci.yml").write_text(wf_code, encoding="utf-8")
    (repo_dir / "requirements.txt").write_text("pytest>=7.0.0\n", encoding="utf-8")


def seed_all_defects() -> dict:
    results = {}
    with tempfile.TemporaryDirectory(prefix="devaura_phase11_seed_") as tmp_dir:
        clone_url = f"https://x-access-token:{TOKEN.strip()}@github.com/{OWNER}/{REPO_NAME}.git"
        print(f"[*] Cloning {OWNER}/{REPO_NAME}...")
        subprocess.run(["git", "clone", clone_url, tmp_dir], check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Devaura Bot"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "bot@devaura.internal"], cwd=tmp_dir, check=True)

        repo_path = Path(tmp_dir)

        # 1. Update main branch with universal CI
        subprocess.run(["git", "checkout", "main"], cwd=tmp_dir, check=True)
        setup_universal_ci_on_main(repo_path)
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "chore: update universal CI workflow for Phase 11"], cwd=tmp_dir, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=tmp_dir, check=True)
        main_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_dir, text=True).strip()
        print(f"[+] Updated main with universal CI: {main_sha[:8]}")

        # -------------------------------------------------------------
        # Branch base/e2e-001: Pricing volume discount bug
        # -------------------------------------------------------------
        print("[*] Creating branch base/e2e-001...")
        subprocess.run(["git", "checkout", "-B", "base/e2e-001", "main"], cwd=tmp_dir, check=True)
        
        # Clean existing source dirs
        for d in ["math_service", "auth_service", "order_pipeline", "inventory_service", "telemetry_service", "storage_service"]:
            p = repo_path / d
            if p.exists():
                shutil.rmtree(p)
        tests_p = repo_path / "tests"
        if tests_p.exists():
            shutil.rmtree(tests_p)
        tests_p.mkdir(parents=True, exist_ok=True)
        (tests_p / "__init__.py").write_text("", encoding="utf-8")

        pkg_001 = repo_path / "pricing_service"
        pkg_001.mkdir(parents=True, exist_ok=True)
        (pkg_001 / "__init__.py").write_text('"""Pricing service package."""\n', encoding="utf-8")
        calc_code = '''"""Pricing service volume calculator."""

def calculate_bulk_discount(units: int, unit_price: float) -> float:
    """Calculate total discounted price based on order volume.
    
    Tiers:
    - 1 to 9 units: 0% discount
    - 10 to 49 units: 10% discount
    - 50 to 99 units: 20% discount (DEFECT: coded as 0.02 instead of 0.20)
    - 100+ units: 30% discount
    """
    if units < 0 or unit_price < 0:
        raise ValueError("Units and unit_price must be non-negative")
    if units == 0:
        return 0.0

    if units < 10:
        discount = 0.0
    elif units < 50:
        discount = 0.10
    elif units < 100:
        discount = 0.02  # DEFECT: Should be 0.20 (20% discount)
    else:
        discount = 0.30

    total = units * unit_price * (1.0 - discount)
    return round(total, 2)
'''
        (pkg_001 / "calculator.py").write_text(calc_code, encoding="utf-8")

        test_001 = '''"""Reproduction test suite for pricing volume discount."""
import pytest
from pricing_service.calculator import calculate_bulk_discount

def test_tier_1_to_9_no_discount():
    assert calculate_bulk_discount(5, 10.0) == 50.0

def test_tier_10_to_49_discount():
    assert calculate_bulk_discount(20, 10.0) == 180.0

def test_tier_50_to_99_discount():
    """Reproducible defect: 50-99 units should receive 20% discount."""
    # 60 units * 10.0 = 600.0 * 0.80 = 480.0
    # Defect: yields 588.0 (only 2% discount applied)
    assert calculate_bulk_discount(60, 10.0) == 480.0
'''
        (tests_p / "test_calculator.py").write_text(test_001, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat(pricing): introduce volume discount calculator with E2E-001 defect"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "push", "-f", "origin", "base/e2e-001"], cwd=tmp_dir, check=True)
        sha_001 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_dir, text=True).strip()
        results["E2E-001"] = {"branch": "base/e2e-001", "base_sha": sha_001}
        print(f"[+] base/e2e-001 seeded at {sha_001[:8]}")

        # -------------------------------------------------------------
        # Branch base/e2e-002: Auth token None/metadata edge case bug
        # -------------------------------------------------------------
        print("[*] Creating branch base/e2e-002...")
        subprocess.run(["git", "checkout", "-B", "base/e2e-002", "main"], cwd=tmp_dir, check=True)
        
        for d in ["math_service", "pricing_service", "order_pipeline", "inventory_service", "telemetry_service", "storage_service"]:
            p = repo_path / d
            if p.exists():
                shutil.rmtree(p)
        tests_p = repo_path / "tests"
        if tests_p.exists():
            shutil.rmtree(tests_p)
        tests_p.mkdir(parents=True, exist_ok=True)
        (tests_p / "__init__.py").write_text("", encoding="utf-8")

        pkg_002 = repo_path / "auth_service"
        pkg_002.mkdir(parents=True, exist_ok=True)
        (pkg_002 / "__init__.py").write_text('"""Auth service package."""\n', encoding="utf-8")
        token_code = '''"""Auth token validator implementation."""

class InvalidClaimsError(Exception):
    """Raised when token claims fail validation."""
    pass

class TokenExpiredError(InvalidClaimsError):
    """Raised when token timestamp has expired."""
    pass

def validate_jwt_claims(payload: dict) -> dict:
    """Validate and normalize JWT claim payload.
    
    Required fields: 'sub', 'exp'.
    Optional field: 'metadata' (dict).
    DEFECT: Accesses payload['metadata']['client_id'] without checking
    if 'metadata' is present or None, raising unhandled AttributeError/KeyError.
    """
    if not isinstance(payload, dict):
        raise InvalidClaimsError("Payload must be a dictionary")

    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise InvalidClaimsError("Missing or invalid subject claim 'sub'")

    exp = payload.get("exp")
    if not exp or not isinstance(exp, (int, float)):
        raise InvalidClaimsError("Missing or non-numeric expiration claim 'exp'")
    if exp < 1000000000:
        raise TokenExpiredError("Token has expired")

    # DEFECT: Unhandled None or omitted 'metadata'
    metadata = payload["metadata"]
    client_id = metadata.get("client_id", "default_client")

    return {
        "sub": sub,
        "exp": exp,
        "client_id": client_id,
        "is_valid": True,
    }
'''
        (pkg_002 / "token_validator.py").write_text(token_code, encoding="utf-8")

        test_002 = '''"""Reproduction test suite for auth token validation."""
import pytest
from auth_service.token_validator import validate_jwt_claims, InvalidClaimsError

def test_valid_token_with_metadata():
    payload = {"sub": "user_123", "exp": 2000000000, "metadata": {"client_id": "custom_app"}}
    res = validate_jwt_claims(payload)
    assert res["sub"] == "user_123"
    assert res["client_id"] == "custom_app"
    assert res["is_valid"] is True

def test_missing_optional_metadata():
    """Reproducible defect: Metadata is optional, but omitting it raises KeyError."""
    payload = {"sub": "user_456", "exp": 2000000000}
    res = validate_jwt_claims(payload)
    assert res["sub"] == "user_456"
    assert res["client_id"] == "default_client"
    assert res["is_valid"] is True
'''
        (tests_p / "test_token_validator.py").write_text(test_002, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat(auth): introduce token claims validator with E2E-002 defect"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "push", "-f", "origin", "base/e2e-002"], cwd=tmp_dir, check=True)
        sha_002 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_dir, text=True).strip()
        results["E2E-002"] = {"branch": "base/e2e-002", "base_sha": sha_002}
        print(f"[+] base/e2e-002 seeded at {sha_002[:8]}")

        # -------------------------------------------------------------
        # Branch base/e2e-003: Multi-module order checkout & inventory
        # -------------------------------------------------------------
        print("[*] Creating branch base/e2e-003...")
        subprocess.run(["git", "checkout", "-B", "base/e2e-003", "main"], cwd=tmp_dir, check=True)
        
        for d in ["math_service", "pricing_service", "auth_service", "telemetry_service", "storage_service"]:
            p = repo_path / d
            if p.exists():
                shutil.rmtree(p)
        tests_p = repo_path / "tests"
        if tests_p.exists():
            shutil.rmtree(tests_p)
        tests_p.mkdir(parents=True, exist_ok=True)
        (tests_p / "__init__.py").write_text("", encoding="utf-8")

        inv_pkg = repo_path / "inventory_service"
        inv_pkg.mkdir(parents=True, exist_ok=True)
        (inv_pkg / "__init__.py").write_text('"""Inventory service package."""\n', encoding="utf-8")
        stock_code = '''"""Inventory service stock management."""

_STOCK = {
    "SKU-100": 50,
    "SKU-200": 10,
}

def reserve_inventory(sku: str, quantity: int) -> dict:
    """Reserve inventory for a given SKU.
    
    Returns:
        dict: {"status": "CONFIRMED", "reserved": quantity, "sku": sku} on success,
              {"status": "OUT_OF_STOCK", "reserved": 0, "sku": sku} on failure.
    """
    if quantity <= 0:
        raise ValueError("Quantity must be positive")
    available = _STOCK.get(sku, 0)
    if available >= quantity:
        _STOCK[sku] = available - quantity
        return {"status": "CONFIRMED", "reserved": quantity, "sku": sku}
    return {"status": "OUT_OF_STOCK", "reserved": 0, "sku": sku}
'''
        (inv_pkg / "stock.py").write_text(stock_code, encoding="utf-8")

        order_pkg = repo_path / "order_pipeline"
        order_pkg.mkdir(parents=True, exist_ok=True)
        (order_pkg / "__init__.py").write_text('"""Order pipeline package."""\n', encoding="utf-8")
        checkout_code = '''"""Order pipeline checkout processor."""
from inventory_service.stock import reserve_inventory

def process_checkout(order_id: str, sku: str, quantity: int) -> dict:
    """Process an order checkout.
    
    DEFECT:
    1. Calls reserve_inventory with reversed positional arguments: (quantity, sku).
    2. Checks res.get("is_reserved") instead of res.get("status") == "CONFIRMED".
    """
    # DEFECT: Positional argument mismatch (quantity passed as sku, sku passed as quantity)
    res = reserve_inventory(quantity, sku)  # Should be reserve_inventory(sku, quantity)
    
    if not res.get("status") == "CONFIRMED":
        return {"order_id": order_id, "status": "FAILED", "reason": "Inventory reservation failed"}
        
    return {
        "order_id": order_id,
        "sku": sku,
        "quantity": quantity,
        "status": "COMPLETED",
    }
'''
        (order_pkg / "checkout.py").write_text(checkout_code, encoding="utf-8")

        test_003 = '''"""Reproduction test suite for order pipeline checkout."""
import pytest
from order_pipeline.checkout import process_checkout

def test_checkout_reservation_flow():
    """Reproducible defect: Argument transposition causes TypeError in reservation."""
    result = process_checkout(order_id="ORD-1", sku="SKU-100", quantity=2)
    assert result["status"] == "COMPLETED"
    assert result["order_id"] == "ORD-1"
'''
        (tests_p / "test_checkout.py").write_text(test_003, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat(orders): introduce checkout processor with E2E-003 cross-module defect"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "push", "-f", "origin", "base/e2e-003"], cwd=tmp_dir, check=True)
        sha_003 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_dir, text=True).strip()
        results["E2E-003"] = {"branch": "base/e2e-003", "base_sha": sha_003}
        print(f"[+] base/e2e-003 seeded at {sha_003[:8]}")

        # -------------------------------------------------------------
        # Branch base/e2e-004: Telemetry formatter strict ISO-8601 regression
        # -------------------------------------------------------------
        print("[*] Creating branch base/e2e-004...")
        subprocess.run(["git", "checkout", "-B", "base/e2e-004", "main"], cwd=tmp_dir, check=True)
        
        for d in ["math_service", "pricing_service", "auth_service", "order_pipeline", "inventory_service", "storage_service"]:
            p = repo_path / d
            if p.exists():
                shutil.rmtree(p)
        tests_p = repo_path / "tests"
        if tests_p.exists():
            shutil.rmtree(tests_p)
        tests_p.mkdir(parents=True, exist_ok=True)
        (tests_p / "__init__.py").write_text("", encoding="utf-8")

        telemetry_pkg = repo_path / "telemetry_service"
        telemetry_pkg.mkdir(parents=True, exist_ok=True)
        (telemetry_pkg / "__init__.py").write_text('"""Telemetry service package."""\n', encoding="utf-8")
        formatter_code = '''"""Telemetry event formatter implementation."""
from datetime import datetime, timezone

def format_telemetry_event(event_name: str, timestamp: datetime, payload: dict) -> dict:
    """Format an event with strict ISO-8601 UTC timestamp and structured payload.
    
    DEFECT:
    Uses strftime('%Y-%m-%d %H:%M:%S') which strips timezone offset and microseconds,
    violating strict ISO-8601 formatting required by downstream log ingestion.
    """
    if not event_name:
        raise ValueError("Event name cannot be empty")
        
    # DEFECT: Non-compliant datetime formatting lacking ISO-8601 'T' and timezone indicator
    ts_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    return {
        "event": event_name,
        "timestamp": ts_str,
        "data": payload or {},
    }
'''
        (telemetry_pkg / "formatter.py").write_text(formatter_code, encoding="utf-8")

        test_004 = '''"""Reproduction test suite for telemetry formatter."""
import re
from datetime import datetime, timezone
import pytest
from telemetry_service.formatter import format_telemetry_event

def test_iso8601_strict_formatting():
    """Reproducible defect: Formatted timestamp must adhere to ISO-8601 standard."""
    dt = datetime(2026, 11, 25, 12, 30, 45, 123456, tzinfo=timezone.utc)
    res = format_telemetry_event("user_login", dt, {"user_id": "usr_99"})
    
    assert res["event"] == "user_login"
    ts = res["timestamp"]
    # ISO-8601 pattern: YYYY-MM-DDTHH:MM:SS(.microseconds)?(Z|+00:00)
    iso_pattern = r"^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?(Z|\\+00:00)$"
    assert re.match(iso_pattern, ts), f"Timestamp '{ts}' does not match strict ISO-8601 format"
'''
        (tests_p / "test_formatter.py").write_text(test_004, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat(telemetry): introduce formatter with E2E-004 ISO-8601 regression"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "push", "-f", "origin", "base/e2e-004"], cwd=tmp_dir, check=True)
        sha_004 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_dir, text=True).strip()
        results["E2E-004"] = {"branch": "base/e2e-004", "base_sha": sha_004}
        print(f"[+] base/e2e-004 seeded at {sha_004[:8]}")

        # -------------------------------------------------------------
        # Branch base/e2e-005: Storage backup security/insufficient evidence defect
        # -------------------------------------------------------------
        print("[*] Creating branch base/e2e-005...")
        subprocess.run(["git", "checkout", "-B", "base/e2e-005", "main"], cwd=tmp_dir, check=True)
        
        for d in ["math_service", "pricing_service", "auth_service", "order_pipeline", "inventory_service", "telemetry_service"]:
            p = repo_path / d
            if p.exists():
                shutil.rmtree(p)
        tests_p = repo_path / "tests"
        if tests_p.exists():
            shutil.rmtree(tests_p)
        tests_p.mkdir(parents=True, exist_ok=True)
        (tests_p / "__init__.py").write_text("", encoding="utf-8")

        storage_pkg = repo_path / "storage_service"
        storage_pkg.mkdir(parents=True, exist_ok=True)
        (storage_pkg / "__init__.py").write_text('"""Storage service package."""\n', encoding="utf-8")
        backup_code = '''"""Storage backup coordinator."""
import os

def run_backup(target_path: str, destination_dir: str) -> bool:
    """Run system backup safely without path traversal or unsafe file access."""
    if ".." in target_path or ".." in destination_dir:
        raise ValueError("Path traversal detected")
    if target_path.startswith("/etc") or target_path.startswith(".env"):
        raise PermissionError("Access to protected system path denied")
    return True
'''
        (storage_pkg / "backup.py").write_text(backup_code, encoding="utf-8")

        test_005 = '''"""Reproduction test suite for storage backup."""
import pytest
from storage_service.backup import run_backup

def test_safe_backup():
    assert run_backup("data/file.txt", "backups") is True

def test_unsafe_backup_rejection():
    with pytest.raises(PermissionError):
        run_backup(".env", "backups")
'''
        (tests_p / "test_backup.py").write_text(test_005, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "feat(storage): introduce backup coordinator with E2E-005 safety boundary"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "push", "-f", "origin", "base/e2e-005"], cwd=tmp_dir, check=True)
        sha_005 = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_dir, text=True).strip()
        results["E2E-005"] = {"branch": "base/e2e-005", "base_sha": sha_005}
        print(f"[+] base/e2e-005 seeded at {sha_005[:8]}")

        # Switch back to main
        subprocess.run(["git", "checkout", "main"], cwd=tmp_dir, check=True)

    print("\n[DONE] All 5 defect branches seeded successfully on GitHub!")
    for defect_id, info in results.items():
        print(f"  {defect_id}: branch={info['branch']}, base_sha={info['base_sha'][:8]}")
    return results


if __name__ == "__main__":
    seed_all_defects()
