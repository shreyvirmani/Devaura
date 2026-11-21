"""Devaura Git Provider Interface and Exception Hierarchy.

Provides an extensible abstraction over Git hosting services (GitHub, GitLab,
Bitbucket, and Mock providers for testing) ensuring zero vendor lock-in.
"""

from abc import ABC, abstractmethod
import time
from typing import List, Optional
from integrations.github.models import (
    BranchInfo,
    CIStatusInfo,
    CommitInfo,
    ProviderType,
    PullRequestPayload,
    PullRequestResult,
    ReviewInfo,
)


# -----------------------------------------------------------------------------
# Exception Hierarchy
# -----------------------------------------------------------------------------
class GitProviderError(Exception):
    """Base exception for all Git provider interactions."""

    def __init__(self, message: str, code: str = "GIT_PROVIDER_ERROR", status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class GitHubAuthRequiredError(GitProviderError):
    """Raised when GitHub token or authentication credentials are missing or invalid."""

    def __init__(self, message: str = "GitHub authentication required. Set GITHUB_TOKEN environment variable."):
        super().__init__(message=message, code="AUTHENTICATION_FAILURE", status_code=401)


class GitAuthorizationError(GitProviderError):
    """Raised when credentials lack write permissions to the repository."""

    def __init__(self, message: str = "Insufficient permissions for target repository."):
        super().__init__(message=message, code="AUTHORIZATION_FAILURE", status_code=403)


class GitRateLimitError(GitProviderError):
    """Raised when GitHub API rate limits are exceeded."""

    def __init__(self, message: str = "GitHub API rate limit exceeded.", retry_after_seconds: int = 60):
        super().__init__(message=message, code="RATE_LIMITED", status_code=429)
        self.retry_after_seconds = retry_after_seconds
        self.reset_timestamp = int(time.time()) + retry_after_seconds


class GitNetworkError(GitProviderError):
    """Raised on connection timeout or unresolvable network errors."""

    def __init__(self, message: str = "Network error connecting to Git provider."):
        super().__init__(message=message, code="NETWORK_FAILURE", status_code=503)


class BranchAlreadyExistsError(GitProviderError):
    """Raised when the repair branch already exists on the remote."""

    def __init__(self, branch_name: str):
        super().__init__(
            message=f"Branch '{branch_name}' already exists on remote.",
            code="BRANCH_EXISTS",
            status_code=409,
        )
        self.branch_name = branch_name


class GitConflictError(GitProviderError):
    """Raised when git changes conflict with remote base revision."""

    def __init__(self, message: str = "Git conflict detected."):
        super().__init__(message=message, code="GIT_CONFLICT", status_code=409)


class BaseRevisionChangedError(GitProviderError):
    """Raised when remote base branch has advanced beyond the verified base revision."""

    def __init__(self, verified_sha: str, remote_sha: str):
        super().__init__(
            message=f"Base revision has changed on remote: verified against '{verified_sha[:8]}', remote is at '{remote_sha[:8]}'. Automatic rebase prohibited.",
            code="BASE_REVISION_CHANGED",
            status_code=409,
        )
        self.verified_sha = verified_sha
        self.remote_sha = remote_sha


class BranchPushError(GitProviderError):
    """Raised when pushing a branch to remote fails."""

    def __init__(self, message: str = "Failed to push branch to remote repository."):
        super().__init__(message=message, code="PUSH_FAILURE", status_code=502)


class PullRequestCreationError(GitProviderError):
    """Raised when PR creation endpoint returns an unexpected error."""

    def __init__(self, message: str = "Failed to create pull request."):
        super().__init__(message=message, code="PR_CREATION_FAILURE", status_code=502)


class PullRequestAlreadyExistsError(GitProviderError):
    """Raised when a pull request for this branch/repair already exists."""

    def __init__(self, pr_number: int, pr_url: str):
        super().__init__(
            message=f"Pull request already exists: #{pr_number} ({pr_url}).",
            code="PR_ALREADY_EXISTS",
            status_code=409,
        )
        self.pr_number = pr_number
        self.pr_url = pr_url
        self.existing_pr_number = pr_number
        self.existing_url = pr_url


class SecurityBlockError(GitProviderError):
    """Raised when security audit detects forbidden files or credentials."""

    def __init__(self, message: str = "Security policy violation blocked operation."):
        super().__init__(message=message, code="SECURITY_BLOCK", status_code=403)


# -----------------------------------------------------------------------------
# Abstract Git Provider
# -----------------------------------------------------------------------------
class GitProvider(ABC):
    """Abstract Base Class for Git hosting providers."""

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Identifier of the provider."""
        pass

    @abstractmethod
    async def get_branch(self, owner: str, repo: str, branch: str) -> Optional[BranchInfo]:
        """Fetch remote branch details or return None if not found."""
        pass

    @abstractmethod
    async def create_branch(self, owner: str, repo: str, branch: str, base_sha: str) -> BranchInfo:
        """Create a new branch pointing to base_sha."""
        pass

    @abstractmethod
    async def push_branch(
        self,
        owner: str,
        repo: str,
        branch: str,
        local_repo_path: str,
    ) -> bool:
        """Push a local branch to the remote repository."""
        pass

    @abstractmethod
    async def find_existing_pr(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> Optional[PullRequestResult]:
        """Search for an existing open pull request matching head and base branches."""
        pass

    @abstractmethod
    async def create_pull_request(self, payload: PullRequestPayload) -> PullRequestResult:
        """Open a new pull request on the provider."""
        pass

    @abstractmethod
    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequestResult:
        """Retrieve latest details for a pull request."""
        pass

    @abstractmethod
    async def get_ci_status(self, owner: str, repo: str, commit_sha: str) -> CIStatusInfo:
        """Retrieve CI check-run status for a commit."""
        pass

    @abstractmethod
    async def get_reviews(self, owner: str, repo: str, pr_number: int) -> ReviewInfo:
        """Retrieve review decision status for a pull request."""
        pass

    async def get_review_status(self, owner: str, repo: str, pr_number: int) -> ReviewInfo:
        """Alias for get_reviews."""
        return await self.get_reviews(owner=owner, repo=repo, pr_number=pr_number)
