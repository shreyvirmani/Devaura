"""Devaura Git & GitHub Integration Domain Models.

Defines provider-agnostic data contracts for repository operations,
branch management, commit creation, pull requests, and CI/review status.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProviderType(str, Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    MOCK = "mock"


class PullRequestState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"


class CIStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"
    UNKNOWN = "unknown"


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    COMMENTED = "commented"
    UNKNOWN = "unknown"


class BranchInfo(BaseModel):
    """Metadata regarding a Git branch on the remote provider."""
    model_config = ConfigDict(extra="ignore")

    name: str
    sha: str
    is_protected: bool = False
    exists: bool = True
    is_current: bool = False


class CommitInfo(BaseModel):
    """Metadata regarding a Git commit created on a branch."""
    model_config = ConfigDict(extra="ignore")

    sha: str
    message: str
    author_name: str
    author_email: str
    created_at: datetime = Field(default_factory=utc_now)

    @property
    def author(self) -> str:
        return f"{self.author_name} <{self.author_email}>"


class PullRequestPayload(BaseModel):
    """Parameters required to open a pull request on the Git provider."""
    model_config = ConfigDict(extra="ignore")

    owner: str
    repo: str
    title: str
    body: str
    head_branch: str
    base_branch: str = "main"
    draft: bool = False


class CICheckInfo(BaseModel):
    """Individual CI check status representation."""
    model_config = ConfigDict(extra="ignore")

    name: str = "check"
    check_name: Optional[str] = None
    status: str = "completed"
    conclusion: Optional[str] = "success"
    details_url: Optional[str] = None

    def model_post_init(self, __context: Any) -> None:
        if self.check_name is None:
            self.check_name = self.name
        elif not self.name or self.name == "check":
            self.name = self.check_name


class CIStatusInfo(BaseModel):
    """CI/CD check run status observation."""
    model_config = ConfigDict(extra="ignore")

    state: CIStatus = CIStatus.PENDING
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    details_url: Optional[str] = None
    summary: str = ""
    checks: List[CICheckInfo] = Field(default_factory=list)

    @property
    def overall_status(self) -> CIStatus:
        return self.state


class ReviewInfo(BaseModel):
    """Pull request review status observation."""
    model_config = ConfigDict(extra="ignore")

    status: ReviewStatus = ReviewStatus.PENDING
    review_count: int = 0
    approvals_count: int = 0
    changes_requested_count: int = 0
    comments_count: int = 0

    @property
    def review_status(self) -> ReviewStatus:
        return self.status


class PullRequestResult(BaseModel):
    """Standardized representation of a pull request across Git providers."""
    model_config = ConfigDict(extra="ignore")

    provider: ProviderType = ProviderType.GITHUB
    owner: str
    repo: str
    pr_number: int
    pr_url: str
    title: str
    body: str
    head_branch: str
    base_branch: str
    head_sha: Optional[str] = None
    base_sha: Optional[str] = None
    state: PullRequestState = PullRequestState.OPEN
    is_draft: bool = False
    mergeable: Optional[bool] = None
    ci_status: CIStatusInfo = Field(default_factory=CIStatusInfo)
    review_status: ReviewInfo = Field(default_factory=ReviewInfo)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    provider_metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def commit_sha(self) -> Optional[str]:
        return self.head_sha
