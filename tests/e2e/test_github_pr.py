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
import base64
import httpx
import dotenv
import pytest
from integrations.github.client import GitHubClient
from integrations.github.models import PullRequestPayload, PullRequestState

dotenv.load_dotenv()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not os.getenv("RUN_GITHUB_E2E"),
    reason="Requires RUN_GITHUB_E2E=1 and valid GITHUB_TOKEN in environment",
)
async def test_live_github_pr_lifecycle():
    token = os.getenv("GITHUB_TOKEN")
    owner = os.getenv("GITHUB_OWNER", "shreyvirmani")
    repo = os.getenv("GITHUB_REPO", "devaura-disposable-e2e")
    run_id = str(uuid.uuid4())[:8]
    branch_name = f"devaura/test-pr-{run_id}"

    client = GitHubClient(token=token)

    try:
        # 1. Fetch default branch info
        repo_info = await client.get_repository(owner=owner, repo=repo)
        default_branch_name = repo_info["default_branch"]
        base_branch = await client.get_branch(owner=owner, repo=repo, branch=default_branch_name)
        assert base_branch is not None
        assert base_branch.name in {"main", "master"}
        assert len(base_branch.sha) >= 7

        # 2. Base branch protection check: pushing directly to main must be blocked
        with pytest.raises(Exception):
            await client.push_branch(
                owner=owner,
                repo=repo,
                branch=base_branch.name,
                local_repo_path=".",
            )

        # 3. Create test branch
        created_branch = await client.create_branch(
            owner=owner,
            repo=repo,
            branch=branch_name,
            base_sha=base_branch.sha,
        )
        assert created_branch.name == branch_name

        # 3b. Push probe commit via GitHub Contents API so branch has >= 1 commit ahead of main
        content_url = f"{client.base_url}/repos/{owner}/{repo}/contents/e2e_probe_{run_id}.txt"
        commit_payload = {
            "message": f"test: e2e probe commit {run_id}",
            "content": base64.b64encode(b"probe").decode(),
            "branch": branch_name,
        }
        async with httpx.AsyncClient(timeout=client.timeout_seconds) as http_c:
            await http_c.put(content_url, headers=client._get_headers(), json=commit_payload)

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
        review_status = await client.get_reviews(
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
        await client.delete_branch(owner=owner, repo=repo, branch=branch_name)

    finally:
        pass
