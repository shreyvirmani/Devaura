"""Pre-flight verification script for a hosted Devaura staging API deployment.

Usage:
    python scripts/verify_staging_readiness.py --api-url https://devaura-staging-api.onrender.com
"""

from __future__ import annotations

import argparse
import sys
import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Devaura hosted staging liveness and readiness.")
    parser.add_argument("--api-url", required=True, help="Base URL of the hosted staging API (no trailing slash).")
    args = parser.parse_args()
    base = args.api_url.rstrip("/")

    with httpx.Client(timeout=15.0) as client:
        live = client.get(f"{base}/api/v1/health/live")
        print(f"GET /api/v1/health/live -> {live.status_code} {live.text}")
        if live.status_code != 200 or live.json().get("live") != "true":
            return 1

        ready = client.get(f"{base}/api/v1/health/ready")
        print(f"GET /api/v1/health/ready -> {ready.status_code} {ready.text}")
        if ready.status_code != 200 or ready.json().get("ready") != "true":
            return 1

    print("Staging liveness & readiness verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
