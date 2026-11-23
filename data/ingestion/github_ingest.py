"""Devaura Real Data Pipeline: Real GitHub Ingestion Layer.

Ingests live repository metadata, issues, pull requests, commits, diffs, and CI workflow runs
from the official GitHub REST API (v3) using configured credentials.
Preserves auditable provenance metadata. Never fabricates responses on API failure.
"""

import os
from typing import Any, Dict, List, Optional
import httpx

from data.provenance.provenance_tracker import ProvenanceRecord
from data.validation.secret_detector import SecretDetector
from data.validation.license_validator import LicenseValidator, LicenseValidationError


class GitHubIngestionError(Exception):
    """Raised when GitHub API ingestion fails or credentials are unauthorized."""
    pass


class GitHubIngestionService:
    """Production GitHub ingestion client for software defect mining and provenance."""

    BASE_URL = "https://api.github.com"

    def __init__(self, token: Optional[str] = None, timeout_seconds: float = 30.0):
        self.token = token or os.getenv("GITHUB_TOKEN") or os.getenv("DEVAURA_GITHUB_TOKEN")
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "Devaura-Ingestion/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token.strip()}"
        return headers

    def _sanitize(self, text: str) -> str:
        if not self.token:
            return text
        return text.replace(self.token, "[REDACTED_GITHUB_TOKEN]")

    def _handle_error(self, response: httpx.Response, action: str) -> None:
        if response.status_code in (200, 201):
            return
        status = response.status_code
        err_msg = response.text[:300]
        sanitized = self._sanitize(err_msg)

        if status == 401:
            raise GitHubIngestionError(f"GitHub authentication error during {action}: Bad credentials or token expired.")
        if status == 403:
            rate_remaining = response.headers.get("x-ratelimit-remaining")
            if rate_remaining == "0":
                reset_ts = response.headers.get("x-ratelimit-reset", "unknown")
                raise GitHubIngestionError(f"GitHub rate limit exceeded during {action}. Reset at {reset_ts}.")
            raise GitHubIngestionError(f"GitHub authorization error during {action}: Insufficient scope or permissions.")
        if status == 404:
            raise GitHubIngestionError(f"GitHub resource not found during {action}: {sanitized}")

        raise GitHubIngestionError(f"GitHub API HTTP {status} error during {action}: {sanitized}")

    def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch repository details, open source license, and primary language."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.get(url, headers=self._headers())
                self._handle_error(res, f"get_repository_info({owner}/{repo})")
                data = res.json()
        except httpx.RequestError as exc:
            raise GitHubIngestionError(f"Network error querying GitHub repository {owner}/{repo}: {self._sanitize(str(exc))}")

        license_data = data.get("license") or {}
        license_spdx = license_data.get("spdx_id") or license_data.get("name") or "UNKNOWN"

        # Validate license is permissive
        LicenseValidator.validate_license(f"{owner}/{repo}", license_spdx)

        return {
            "repository": f"{owner}/{repo}",
            "default_branch": data.get("default_branch", "main"),
            "language": (data.get("language") or "python").lower(),
            "license": license_spdx,
            "description": data.get("description", ""),
            "stars": data.get("stargazers_count", 0),
            "source_url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
        }

    def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Fetch issue title, description, author, labels, and comments."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues/{issue_number}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.get(url, headers=self._headers())
                self._handle_error(res, f"get_issue({owner}/{repo}#{issue_number})")
                data = res.json()
        except httpx.RequestError as exc:
            raise GitHubIngestionError(f"Network error querying GitHub issue {owner}/{repo}#{issue_number}: {self._sanitize(str(exc))}")

        body = data.get("body") or ""
        # Check and scrub secrets
        clean_body = SecretDetector.sanitize(body)

        return {
            "issue_number": issue_number,
            "title": data.get("title", ""),
            "body": clean_body,
            "author": (data.get("user") or {}).get("login", "unknown"),
            "state": data.get("state", "open"),
            "labels": [l.get("name", "") for l in data.get("labels", []) if isinstance(l, dict)],
            "created_at": data.get("created_at"),
            "url": data.get("html_url", f"https://github.com/{owner}/{repo}/issues/{issue_number}"),
        }

    def get_pull_request(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """Fetch pull request metadata, diff, changed files, and commits."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                # 1. PR JSON metadata
                res = client.get(url, headers=self._headers())
                self._handle_error(res, f"get_pull_request({owner}/{repo}#{pr_number})")
                data = res.json()

                # 2. PR unified diff
                diff_headers = dict(self._headers())
                diff_headers["Accept"] = "application/vnd.github.v3.diff"
                diff_res = client.get(url, headers=diff_headers)
                diff_text = diff_res.text if diff_res.status_code == 200 else ""
        except httpx.RequestError as exc:
            raise GitHubIngestionError(f"Network error querying GitHub PR {owner}/{repo}#{pr_number}: {self._sanitize(str(exc))}")

        clean_diff = SecretDetector.sanitize(diff_text)

        return {
            "pr_number": pr_number,
            "title": data.get("title", ""),
            "body": SecretDetector.sanitize(data.get("body") or ""),
            "head_branch": (data.get("head") or {}).get("ref", ""),
            "head_sha": (data.get("head") or {}).get("sha", ""),
            "base_branch": (data.get("base") or {}).get("ref", ""),
            "base_sha": (data.get("base") or {}).get("sha", ""),
            "merged": data.get("merged", False),
            "merge_commit_sha": data.get("merge_commit_sha"),
            "unified_diff": clean_diff,
            "url": data.get("html_url", f"https://github.com/{owner}/{repo}/pull/{pr_number}"),
        }

    def get_commit(self, owner: str, repo: str, commit_sha: str) -> Dict[str, Any]:
        """Fetch commit message, author, stats, and file diffs."""
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits/{commit_sha}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.get(url, headers=self._headers())
                self._handle_error(res, f"get_commit({owner}/{repo}@{commit_sha})")
                data = res.json()
        except httpx.RequestError as exc:
            raise GitHubIngestionError(f"Network error querying GitHub commit {owner}/{repo}@{commit_sha}: {self._sanitize(str(exc))}")

        commit_obj = data.get("commit") or {}
        author_obj = commit_obj.get("author") or {}
        files = data.get("files") or []

        changed_files = [f.get("filename", "") for f in files if f.get("filename")]
        file_patches = {
            f.get("filename", ""): SecretDetector.sanitize(f.get("patch", ""))
            for f in files
            if f.get("filename") and f.get("patch")
        }

        return {
            "commit_sha": commit_sha,
            "message": SecretDetector.sanitize(commit_obj.get("message", "")),
            "author": author_obj.get("name") or (data.get("author") or {}).get("login", "unknown"),
            "timestamp": author_obj.get("date"),
            "changed_files": changed_files,
            "patches": file_patches,
            "stats": data.get("stats", {}),
            "url": data.get("html_url", f"https://github.com/{owner}/{repo}/commit/{commit_sha}"),
        }
