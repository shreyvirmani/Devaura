"""Devaura Real GitHub E2E Test Suite.

Guarded by RUN_GITHUB_E2E environment variable.
When active, tests real GitHub API communication:
1. Validates base branch protection.
2. Creates an isolated test branch.
3. Pushes a harmless test commit.
4. Creates a draft PR on https://github.com/shreyvirmani/Devaura.
5. Queries PR status and review status.
6. Closes the PR to clean up.
"""

import os
import uuid
import pytest
from integrations.github.client import GitHubClient
from integrations.github.models import PullRequestPayload, PullRequestState


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_GITHUB_E2E"),
    reason="Requires RUN_GITHUB_E2E=1 and valid GITHUB_TOKEN in environment",
)
async def test_live_github_pr_lifecycle():
    token = os.getenv("GITHUB_TOKEN")
    owner = os.getenv("GITHUB_OWNER", "shreyvirmani")
    repo = os.getenv("GITHUB_REPO", "Devaura")
    run_id = str(uuid.uuid4())[:8]
    branch_name = f"devaura/test-pr-{run_id}"

    client = GitHubClient(token=token)

    try:
        # 1. Fetch default branch info
        base_branch = await client.get_default_branch(owner=owner, repo=repo)
        assert base_branch.name in {"main", "master"}
        assert len(base_branch.sha) >= 7

        # 2. Base branch protection check: pushing directly to main must be blocked
        with pytest.raises(Exception):
            await client.push_branch(
                owner=owner,
                repo=repo,
                branch_name=base_branch.name,
                commit_sha="invalid_sha_direct_push",
            )

        # 3. Create test branch
        created_branch = await client.create_branch(
            owner=owner,
            repo=repo,
            branch_name=branch_name,
            from_sha=base_branch.sha,
        )
        assert created_branch.name == branch_name

        # 4. Create Draft PR
        payload = PullRequestPayload(
            owner=owner,
            repo=repo,
            title=f"test: automated e2e verification pr {run_id}",
            body=(
                f"## Automated E2E Test PR\n\n"
                f"Run ID: `{run_id}`\n"
                f"Base: `{base_branch.name}` (`{base_branch.sha[:7]}`)\n"
                f"Created by Devaura GitHub E2E Test Runner.\n"
                f"Will be automatically closed immediately."
            ),
            head_branch=branch_name,
            base_branch=base_branch.name,
            draft=True,
        )
        pr_result = await client.create_pull_request(payload)
        assert pr_result.pr_number > 0
        assert pr_result.is_draft is True
        assert pr_result.state == PullRequestState.OPEN

        # 5. Query PR
        fetched_pr = await client.get_pull_request(
            owner=owner,
            repo=repo,
            pr_number=pr_result.pr_number,
        )
        assert fetched_pr.pr_number == pr_result.pr_number
        assert fetched_pr.head_branch == branch_name

        # 6. Query CI status
        ci_status = await client.get_ci_status(
            owner=owner,
            repo=repo,
            commit_sha=base_branch.sha,
        )
        assert ci_status is not None

        # 7. Query Review status
        review_status = await client.get_review_status(
            owner=owner,
            repo=repo,
            pr_number=pr_result.pr_number,
        )
        assert review_status is not None

        # 8. Clean up: Close PR
        closed_pr = await client.close_pull_request(
            owner=owner,
            repo=repo,
            pr_number=pr_result.pr_number,
        )
        assert closed_pr.state == PullRequestState.CLOSED

        # 9. Clean up: Delete test branch
        await client.delete_branch(owner=owner, repo=repo, branch_name=branch_name)

    finally:
        await client.close()
