"""
Devaura Disposable Test Repository Setup Script (Phase 10).

Creates and initializes shreyvirmani/devaura-disposable-e2e with a reproducible defect
and a GitHub Actions CI workflow.
"""

import os
import sys
import time
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
    "User-Agent": "Devaura-Phase10-Setup",
}


def create_or_verify_repo() -> bool:
    print(f"[*] Checking if repository {OWNER}/{REPO_NAME} exists...")
    r = httpx.get(f"{API_BASE}/repos/{OWNER}/{REPO_NAME}", headers=HEADERS)
    if r.status_code == 200:
        print(f"[+] Repository {OWNER}/{REPO_NAME} already exists.")
        return True
    elif r.status_code == 404:
        print(f"[*] Creating repository {OWNER}/{REPO_NAME}...")
        payload = {
            "name": REPO_NAME,
            "description": "Devaura E2E Repair Lifecycle Disposable Validation Repository",
            "private": False,
            "auto_init": True,
        }
        create_res = httpx.post(f"{API_BASE}/user/repos", headers=HEADERS, json=payload)
        if create_res.status_code in (200, 201):
            print(f"[+] Successfully created {OWNER}/{REPO_NAME} on GitHub.")
            time.sleep(3)  # Wait for GitHub to provision main branch
            return True
        else:
            print(f"[-] Failed to create repository: {create_res.status_code} {create_res.text}")
            return False
    else:
        print(f"[-] Unexpected GitHub response: {r.status_code} {r.text}")
        return False


def seed_reproducible_defect_and_ci() -> str:
    print("[*] Seeding repository with reproducible defect and GitHub Actions CI...")
    with tempfile.TemporaryDirectory(prefix="devaura_seed_") as tmp_dir:
        clone_url = f"https://x-access-token:{TOKEN.strip()}@github.com/{OWNER}/{REPO_NAME}.git"
        
        # Clone
        subprocess.run(["git", "clone", clone_url, tmp_dir], check=True, capture_output=True)
        
        # Configure git identity for disposable commits
        subprocess.run(["git", "config", "user.name", "Devaura Bot"], cwd=tmp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "bot@devaura.internal"], cwd=tmp_dir, check=True)
        
        # 1. math_service/calculator.py
        math_service_dir = Path(tmp_dir) / "math_service"
        math_service_dir.mkdir(parents=True, exist_ok=True)
        
        (math_service_dir / "__init__.py").write_text('"""Math service package."""\n', encoding="utf-8")
        calc_code = (
            '"""Math service calculator implementation."""\n\n'
            'def calculate_discount(price: float, tier: str) -> float:\n'
            '    """Calculate discounted price based on customer tier.\n'
            '    \n'
            '    Tiers:\n'
            '    - \'standard\': 5% discount\n'
            '    - \'premium\': 15% discount\n'
            '    - \'enterprise\': 25% discount\n'
            '    """\n'
            '    if price < 0:\n'
            '        raise ValueError("Price cannot be negative")\n'
            '    \n'
            '    if tier == "standard":\n'
            '        discount = 0.05\n'
            '    elif tier == "premium":\n'
            '        discount = 0.15\n'
            '    elif tier == "enterprise":\n'
            '        discount = 0.05  # DEFECT: Should be 0.25 (enterprise receives 25% discount)\n'
            '    else:\n'
            '        discount = 0.0\n'
            '        \n'
            '    return round(price * (1.0 - discount), 2)\n'
        )
        (math_service_dir / "calculator.py").write_text(calc_code, encoding="utf-8")
        
        # 2. tests/test_calculator.py
        tests_dir = Path(tmp_dir) / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        test_code = (
            '"""Reproduction test suite for math service calculator."""\n'
            'import pytest\n'
            'from math_service.calculator import calculate_discount\n\n'
            'def test_standard_discount():\n'
            '    assert calculate_discount(100.0, "standard") == 95.0\n\n'
            'def test_premium_discount():\n'
            '    assert calculate_discount(100.0, "premium") == 85.0\n\n'
            'def test_enterprise_discount_failure():\n'
            '    """Reproducible defect: Enterprise customers should receive 25% discount."""\n'
            '    # Defect: Returns 95.0 instead of 75.0\n'
            '    assert calculate_discount(100.0, "enterprise") == 75.0\n'
        )
        (tests_dir / "test_calculator.py").write_text(test_code, encoding="utf-8")
        
        # 3. .github/workflows/ci.yml
        wf_dir = Path(tmp_dir) / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_code = (
            'name: CI\n\n'
            'on:\n'
            '  push:\n'
            '    branches: [ "main" ]\n'
            '  pull_request:\n'
            '    branches: [ "main" ]\n\n'
            'jobs:\n'
            '  test:\n'
            '    runs-on: ubuntu-latest\n'
            '    steps:\n'
            '    - uses: actions/checkout@v4\n'
            '    - name: Set up Python\n'
            '      uses: actions/setup-python@v5\n'
            '      with:\n'
            '        python-version: "3.11"\n'
            '    - name: Install dependencies\n'
            '      run: |\n'
            '        python -m pip install --upgrade pip\n'
            '        pip install pytest\n'
            '    - name: Run tests\n'
            '      run: |\n'
            '        pytest\n'
        )
        (wf_dir / "ci.yml").write_text(wf_code, encoding="utf-8")
        
        # 4. requirements.txt
        (Path(tmp_dir) / "requirements.txt").write_text("pytest>=7.0.0\n", encoding="utf-8")
        
        # 5. README.md
        (Path(tmp_dir) / "README.md").write_text(
            "# Devaura Disposable E2E Test Repository\n\n"
            "This repository is dedicated to verifying the end-to-end Devaura repair lifecycle:\n"
            "- Failure reproduction\n"
            "- Live LLM repair\n"
            "- Sandbox verification\n"
            "- Approval token gate\n"
            "- Git branch & commit\n"
            "- Pull Request creation\n"
            "- CI check status monitoring\n",
            encoding="utf-8"
        )
        
        # Stage, commit, and push
        subprocess.run(["git", "add", "."], cwd=tmp_dir, check=True)
        commit_res = subprocess.run(["git", "commit", "-m", "chore: initialize disposable calculator repo with reproducible defect and CI"], cwd=tmp_dir, capture_output=True, text=True)
        print(f"[+] Git commit: {commit_res.stdout.strip()}")
        
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=tmp_dir, capture_output=True, text=True)
        if push_res.returncode != 0:
            print(f"[-] Push failed: {push_res.stderr}")
            sys.exit(1)
        print("[+] Successfully pushed buggy revision to main.")
        
        rev_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_dir, capture_output=True, text=True, check=True)
        base_sha = rev_res.stdout.strip()
        print(f"[+] Base revision SHA: {base_sha}")
        return base_sha


if __name__ == "__main__":
    if create_or_verify_repo():
        sha = seed_reproducible_defect_and_ci()
        print(f"[DONE] Disposable repository ready at https://github.com/{OWNER}/{REPO_NAME} (base_sha: {sha})")
