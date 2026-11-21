"""Devaura Production GitHub API Client.

Implements GitProvider using the GitHub REST API (v3) via httpx.
Enforces strict secret sanitization, rate limit handling, and structured error mapping.
"""

import os
import re
import subprocess
from typing import Any, Dict, List, Optional
import httpx

from apps.api.logger import logger
from integrations.github.models import (
    BranchInfo,
    CIStatus,
    CIStatusInfo,
    CommitInfo,
    ProviderType,
    PullRequestPayload,
    PullRequestResult,
    PullRequestState,
    ReviewInfo,
    ReviewStatus,
)
from integrations.github.provider import (
    BranchAlreadyExistsError,
    BranchPushError,
    GitAuthorizationError,
    GitConflictError,
    GitNetworkError,
    GitProvider,
    GitRateLimitError,
    GitHubAuthRequiredError,
    PullRequestAlreadyExistsError,
    PullRequestCreationError,
)


class GitHubClient(GitProvider):
    """Production GitProvider implementation for GitHub."""

    DEFAULT_BASE_URL = "https://api.github.com"

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 30.0,
    ):
        self._token = token or os.getenv("GITHUB_TOKEN") or os.getenv("DEVAURA_GITHUB_TOKEN")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GITHUB

    @property
    def is_authenticated(self) -> bool:
        return bool(self._token and len(self._token.strip()) > 0)

    def _get_headers(self) -> Dict[str, str]:
        if not self.is_authenticated:
            raise GitHubAuthRequiredError("GitHub token not configured. Set GITHUB_TOKEN environment variable.")
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token.strip()}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Devaura-Platform/1.0",
        }

    def _sanitize(self, text: str) -> str:
        """Strip any token occurrences from error messages or logs."""
        if not self._token:
            return text
        return text.replace(self._token, "[REDACTED_GITHUB_TOKEN]")

    def _handle_response_error(self, response: httpx.Response, action_description: str) -> None:
        status = response.status_code
        if status == 200 or status == 201:
            return

        rate_limit_remaining = response.headers.get("x-ratelimit-remaining")
        if status == 429 or (status == 403 and rate_limit_remaining == "0"):
            reset_time = response.headers.get("x-ratelimit-reset", "60")
            raise GitRateLimitError(
                f"GitHub rate limit exceeded during {action_description}.",
                retry_after_seconds=60,
            )

        if status == 401:
            raise GitHubAuthRequiredError("GitHub authentication failed: Token is invalid or expired.")

        if status == 403:
            raise GitAuthorizationError(
                f"GitHub authorization failed: Insufficient permissions for {action_description}."
            )

        error_data = {}
        try:
            error_data = response.json()
        except Exception:
            pass

        msg = error_data.get("message", response.text[:200])
        sanitized_msg = self._sanitize(msg)

        if status == 409:
            raise GitConflictError(f"GitHub conflict during {action_description}: {sanitized_msg}")

        if status == 422:
            # Check for existing PR or branch
            errors = error_data.get("errors", [])
            for err in errors:
                if isinstance(err, dict) and "A pull request already exists" in err.get("message", ""):
                    raise PullRequestAlreadyExistsError(0, sanitized_msg)
            raise PullRequestCreationError(f"Unprocessable entity during {action_description}: {sanitized_msg}")

        raise PullRequestCreationError(f"GitHub API error ({status}) during {action_description}: {sanitized_msg}")

    async def get_branch(self, owner: str, repo: str, branch: str) -> Optional[BranchInfo]:
        """Fetch remote branch details from GitHub."""
        url = f"{self.base_url}/repos/{owner}/{repo}/branches/{branch}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 404:
                    return None
                self._handle_response_error(res, f"get_branch({branch})")
                data = res.json()
                commit_sha = data.get("commit", {}).get("sha", "")
                is_protected = data.get("protected", False)
                return BranchInfo(name=branch, sha=commit_sha, is_protected=is_protected, exists=True)
        except httpx.RequestError as exc:
            raise GitNetworkError(f"Network error querying GitHub branch: {self._sanitize(str(exc))}")

    async def create_branch(self, owner: str, repo: str, branch: str, base_sha: str) -> BranchInfo:
        """Create a new git reference for the repair branch."""
        url = f"{self.base_url}/repos/{owner}/{repo}/git/refs"
        payload = {"ref": f"refs/heads/{branch}", "sha": base_sha}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.post(url, headers=self._get_headers(), json=payload)
                if res.status_code == 422:
                    raise BranchAlreadyExistsError(branch)
                self._handle_response_error(res, f"create_branch({branch})")
                data = res.json()
                sha = data.get("object", {}).get("sha", base_sha)
                return BranchInfo(name=branch, sha=sha, is_protected=False, exists=True)
        except httpx.RequestError as exc:
            raise GitNetworkError(f"Network error creating GitHub branch: {self._sanitize(str(exc))}")

    async def push_branch(
        self,
        owner: str,
        repo: str,
        branch: str,
        local_repo_path: str,
    ) -> bool:
        """Push a verified local repair branch to GitHub using authenticated credentials."""
        if not self.is_authenticated:
            raise GitHubAuthRequiredError()

        # Guard: Never push main branch
        if branch in {"main", "master", "develop", "prod", "production"}:
            raise SecurityBlockError(f"Cannot push directly to base branch '{branch}'. Modifying base branch is prohibited.")

        remote_url = f"https://x-access-token:{self._token}@github.com/{owner}/{repo}.git"
        push_cmd = ["git", "push", "-u", remote_url, branch]

        try:
            result = subprocess.run(
                push_cmd,
                cwd=local_repo_path,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
            )
            if result.returncode != 0:
                sanitized_err = self._sanitize(result.stderr or result.stdout)
                logger.error(f"GitHub push failed: {sanitized_err}")
                if "Protected branch" in sanitized_err or "protected" in sanitized_err.lower():
                    raise GitAuthorizationError("Branch is protected by repository rules.")
                if "Everything up-to-date" in sanitized_err:
                    return True
                raise BranchPushError(f"git push failed with exit code {result.returncode}: {sanitized_err[:300]}")
            return True
        except subprocess.TimeoutExpired:
            raise GitNetworkError("git push timed out after 30 seconds.")
        except Exception as e:
            if isinstance(e, GitProviderError):
                raise
            raise BranchPushError(f"Failed to execute git push: {self._sanitize(str(e))}")

    async def find_existing_pr(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> Optional[PullRequestResult]:
        """Check if an open pull request already exists for this branch."""
        # GitHub expects head format: "owner:branch" or just "branch"
        head_query = f"{owner}:{head_branch}"
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls?head={head_query}&base={base_branch}&state=open"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 404:
                    return None
                self._handle_response_error(res, "find_existing_pr")
                prs = res.json()
                if isinstance(prs, list) and len(prs) > 0:
                    return self._parse_pr_json(prs[0], owner, repo)
                return None
        except httpx.RequestError as exc:
            raise GitNetworkError(f"Network error querying GitHub PRs: {self._sanitize(str(exc))}")

    async def create_pull_request(self, payload: PullRequestPayload) -> PullRequestResult:
        """Create a new pull request on GitHub."""
        # 1. Idempotency check: see if PR already open
        existing = await self.find_existing_pr(payload.owner, payload.repo, payload.head_branch, payload.base_branch)
        if existing:
            raise PullRequestAlreadyExistsError(existing.pr_number, existing.pr_url)

        url = f"{self.base_url}/repos/{payload.owner}/{payload.repo}/pulls"
        body_dict = {
            "title": payload.title,
            "body": payload.body,
            "head": payload.head_branch,
            "base": payload.base_branch,
            "draft": payload.draft,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.post(url, headers=self._get_headers(), json=body_dict)
                self._handle_response_error(res, "create_pull_request")
                data = res.json()
                return self._parse_pr_json(data, payload.owner, payload.repo)
        except httpx.RequestError as exc:
            raise GitNetworkError(f"Network error creating pull request: {self._sanitize(str(exc))}")

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequestResult:
        """Retrieve pull request metadata by number."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=self._get_headers())
                self._handle_response_error(res, f"get_pull_request({pr_number})")
                data = res.json()
                return self._parse_pr_json(data, owner, repo)
        except httpx.RequestError as exc:
            raise GitNetworkError(f"Network error retrieving GitHub PR: {self._sanitize(str(exc))}")

    async def get_ci_status(self, owner: str, repo: str, commit_sha: str) -> CIStatusInfo:
        """Fetch check runs status for commit."""
        url = f"{self.base_url}/repos/{owner}/{repo}/commits/{commit_sha}/check-runs"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 404:
                    return CIStatusInfo(state=CIStatus.UNKNOWN, summary="No check runs found.")
                self._handle_response_error(res, f"get_ci_status({commit_sha[:8]})")
                data = res.json()
                check_runs = data.get("check_runs", [])
                total = len(check_runs)
                if total == 0:
                    return CIStatusInfo(state=CIStatus.PENDING, summary="No CI checks triggered yet.")

                passed = sum(1 for c in check_runs if c.get("conclusion") == "success")
                failed = sum(1 for c in check_runs if c.get("conclusion") in {"failure", "timed_out", "action_required"})
                any_running = any(c.get("status") in {"in_progress", "queued"} for c in check_runs)

                if failed > 0:
                    overall_state = CIStatus.FAILURE
                elif any_running:
                    overall_state = CIStatus.RUNNING
                elif passed == total:
                    overall_state = CIStatus.SUCCESS
                else:
                    overall_state = CIStatus.PENDING

                return CIStatusInfo(
                    state=overall_state,
                    total_checks=total,
                    passed_checks=passed,
                    failed_checks=failed,
                    summary=f"{passed}/{total} checks passed",
                )
        except httpx.RequestError:
            return CIStatusInfo(state=CIStatus.UNKNOWN, summary="Could not retrieve CI status.")

    async def get_reviews(self, owner: str, repo: str, pr_number: int) -> ReviewInfo:
        """Fetch review decisions for PR."""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                res = await client.get(url, headers=self._get_headers())
                if res.status_code == 404:
                    return ReviewInfo(status=ReviewStatus.UNKNOWN)
                self._handle_response_error(res, f"get_reviews({pr_number})")
                reviews = res.json()
                if not isinstance(reviews, list) or len(reviews) == 0:
                    return ReviewInfo(status=ReviewStatus.PENDING, review_count=0)

                approvals = sum(1 for r in reviews if r.get("state") == "APPROVED")
                changes_req = sum(1 for r in reviews if r.get("state") == "CHANGES_REQUESTED")
                comments = sum(1 for r in reviews if r.get("state") == "COMMENTED")

                if changes_req > 0:
                    overall = ReviewStatus.CHANGES_REQUESTED
                elif approvals > 0:
                    overall = ReviewStatus.APPROVED
                else:
                    overall = ReviewStatus.PENDING

                return ReviewInfo(
                    status=overall,
                    review_count=len(reviews),
                    approvals_count=approvals,
                    changes_requested_count=changes_req,
                    comments_count=comments,
                )
        except httpx.RequestError:
            return ReviewInfo(status=ReviewStatus.UNKNOWN)

    def _parse_pr_json(self, data: Dict[str, Any], owner: str, repo: str) -> PullRequestResult:
        pr_state = PullRequestState.OPEN
        if data.get("merged", False):
            pr_state = PullRequestState.MERGED
        elif data.get("state") == "closed":
            pr_state = PullRequestState.CLOSED

        return PullRequestResult(
            provider=ProviderType.GITHUB,
            owner=owner,
            repo=repo,
            pr_number=data.get("number", 0),
            pr_url=data.get("html_url", ""),
            title=data.get("title", ""),
            body=data.get("body", "") or "",
            head_branch=data.get("head", {}).get("ref", ""),
            base_branch=data.get("base", {}).get("ref", "main"),
            head_sha=data.get("head", {}).get("sha"),
            base_sha=data.get("base", {}).get("sha"),
            state=pr_state,
            is_draft=data.get("draft", False),
            mergeable=data.get("mergeable"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            provider_metadata={"node_id": data.get("node_id"), "id": data.get("id")},
        )
