"""Devaura Deterministic Mock Git Provider.

Used for rigorous unit, integration, and benchmark testing without external
network dependencies, fake credentials, or mutating remote repositories.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from integrations.github.models import (
    BranchInfo,
    CICheckInfo,
    CIStatus,
    CIStatusInfo,
    ProviderType,
    PullRequestPayload,
    PullRequestResult,
    PullRequestState,
    ReviewInfo,
    ReviewStatus,
)
from integrations.github.provider import (
    BaseRevisionChangedError,
    BranchAlreadyExistsError,
    GitConflictError,
    GitNetworkError,
    GitProvider,
    GitRateLimitError,
    GitHubAuthRequiredError,
    PullRequestAlreadyExistsError,
    PullRequestCreationError,
    SecurityBlockError,
)


class MockGitProvider(GitProvider):
    """In-memory deterministic implementation of GitProvider for testing."""

    def __init__(self, initial_default_branch_sha: str = "main_sha_12345"):
        self._provider_type = ProviderType.MOCK
        self.default_branch_sha = initial_default_branch_sha

        # State storage: key is (owner, repo, branch/pr_number/commit_sha)
        self.branches: Dict[Tuple[str, str, str], BranchInfo] = {
            ("shreyvirmani", "Devaura", "main"): BranchInfo(
                name="main", sha=initial_default_branch_sha, is_protected=True, exists=True
            )
        }
        self.pull_requests: Dict[Tuple[str, str, int], PullRequestResult] = {}
        self.ci_statuses: Dict[Tuple[str, str, str], CIStatusInfo] = {}
        self.reviews: Dict[Tuple[str, str, int], ReviewInfo] = {}
        self.pushed_branches: List[Tuple[str, str, str]] = []
        self._next_pr_number = 101

        # Failure simulation triggers
        self.simulate_auth_failure: bool = False
        self.simulate_rate_limit: bool = False
        self.simulate_network_failure: bool = False
        self.simulate_network_error: bool = False
        self.simulate_conflict: bool = False
        self.simulate_base_change_sha: Optional[str] = None
        self.simulate_pr_creation_failure: bool = False

    def simulate_base_revision_divergence(self, owner: str, repo: str, new_sha: str) -> None:
        """Simulate remote branch advancing while local repair was running."""
        self.simulate_base_change_sha = new_sha
        self.branches[(owner, repo, "main")] = BranchInfo(
            name="main", sha=new_sha, is_protected=True, exists=True
        )

    @property
    def provider_type(self) -> ProviderType:
        return self._provider_type

    def _check_simulated_failures(self) -> None:
        if self.simulate_auth_failure:
            raise GitHubAuthRequiredError("Simulated GitHub authentication failure.")
        if self.simulate_rate_limit:
            raise GitRateLimitError("Simulated GitHub API rate limit exceeded.", retry_after_seconds=30)
        if self.simulate_network_failure or self.simulate_network_error:
            raise GitNetworkError("Simulated network timeout connecting to GitHub.")
        if self.simulate_conflict:
            raise GitConflictError("Simulated merge conflict with base branch.")

    async def get_branch(self, owner: str, repo: str, branch: str) -> Optional[BranchInfo]:
        self._check_simulated_failures()
        if branch == "main" and self.simulate_base_change_sha:
            return BranchInfo(name="main", sha=self.simulate_base_change_sha, is_protected=True, exists=True)
        return self.branches.get((owner, repo, branch))

    async def create_branch(self, owner: str, repo: str, branch: str, base_sha: str) -> BranchInfo:
        self._check_simulated_failures()
        key = (owner, repo, branch)
        if key in self.branches:
            raise BranchAlreadyExistsError(branch)

        info = BranchInfo(name=branch, sha=base_sha, is_protected=False, exists=True)
        self.branches[key] = info
        return info

    async def push_branch(
        self,
        owner: str,
        repo: str,
        branch: Optional[str] = None,
        local_repo_path: str = "",
        branch_name: Optional[str] = None,
        commit_sha: Optional[str] = None,
        **kwargs,
    ) -> bool:
        self._check_simulated_failures()
        target_branch = branch or branch_name or ""
        if (
            target_branch in {"main", "master", "develop", "release", "production"}
            or target_branch.startswith("release/")
            or target_branch.startswith("release-")
        ):
            raise SecurityBlockError(f"Cannot push directly to base branch '{target_branch}'. Modifying base branch is prohibited.")
        key = (owner, repo, target_branch)
        if key not in self.branches:
            # If not pre-created via create_branch, register it
            self.branches[key] = BranchInfo(name=target_branch, sha=commit_sha or "commit_sha_head", is_protected=False, exists=True)
        self.pushed_branches.append(key)
        return True

    async def find_existing_pr(
        self,
        owner: str,
        repo: str,
        head_branch: str,
        base_branch: str = "main",
    ) -> Optional[PullRequestResult]:
        self._check_simulated_failures()
        for (o, r, num), pr in self.pull_requests.items():
            if o == owner and r == repo and pr.head_branch == head_branch and pr.base_branch == base_branch:
                if pr.state == PullRequestState.OPEN:
                    return pr
        return None

    async def create_pull_request(self, payload: PullRequestPayload) -> PullRequestResult:
        self._check_simulated_failures()
        if self.simulate_base_change_sha:
            raise BaseRevisionChangedError(
                verified_sha=self.default_branch_sha,
                remote_sha=self.simulate_base_change_sha,
            )
        if self.simulate_pr_creation_failure:
            raise PullRequestCreationError("Simulated PR creation API error (HTTP 500).")

        # Idempotency check
        existing = await self.find_existing_pr(
            payload.owner, payload.repo, payload.head_branch, payload.base_branch
        )
        if existing:
            raise PullRequestAlreadyExistsError(existing.pr_number, existing.pr_url)

        pr_num = self._next_pr_number
        self._next_pr_number += 1
        pr_url = f"https://github.com/{payload.owner}/{payload.repo}/pull/{pr_num}"

        pr_result = PullRequestResult(
            provider=ProviderType.GITHUB,
            owner=payload.owner,
            repo=payload.repo,
            pr_number=pr_num,
            pr_url=pr_url,
            title=payload.title,
            body=payload.body,
            head_branch=payload.head_branch,
            base_branch=payload.base_branch,
            head_sha="commit_sha_head",
            base_sha=self.default_branch_sha,
            state=PullRequestState.OPEN,
            is_draft=payload.draft,
            mergeable=True,
            ci_status=CIStatusInfo(state=CIStatus.RUNNING, total_checks=3, passed_checks=1, summary="Checks running"),
            review_status=ReviewInfo(status=ReviewStatus.PENDING, review_count=0),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.pull_requests[(payload.owner, payload.repo, pr_num)] = pr_result
        return pr_result

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> PullRequestResult:
        self._check_simulated_failures()
        pr = self.pull_requests.get((owner, repo, pr_number))
        if not pr:
            raise PullRequestCreationError(f"Pull Request #{pr_number} not found.")
        return pr

    async def get_ci_status(self, owner: str, repo: str, commit_sha: str) -> CIStatusInfo:
        self._check_simulated_failures()
        return self.ci_statuses.get(
            (owner, repo, commit_sha),
            CIStatusInfo(
                state=CIStatus.SUCCESS,
                total_checks=3,
                passed_checks=3,
                summary="All checks passed",
                checks=[
                    CICheckInfo(
                        name="devaura/verification",
                        check_name="devaura/verification",
                        status="completed",
                        conclusion="success",
                    )
                ],
            ),
        )

    async def get_reviews(self, owner: str, repo: str, pr_number: int) -> ReviewInfo:
        self._check_simulated_failures()
        return self.reviews.get(
            (owner, repo, pr_number),
            ReviewInfo(status=ReviewStatus.PENDING, review_count=0),
        )

    async def get_review_status(self, owner: str, repo: str, pr_number: int) -> ReviewInfo:
        return await self.get_reviews(owner=owner, repo=repo, pr_number=pr_number)
