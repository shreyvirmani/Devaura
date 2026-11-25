"""Devaura GitHub App Integration Service.

Handles:
1. GitHub App JWT generation (RS256 signed with private key).
2. Short-lived Installation Access Token acquisition and in-memory caching.
3. Accessible repository discovery for authorized installations.
4. Authoritative repository metadata verification (anti-spoofing).
5. HMAC-SHA256 Webhook signature validation.
"""

from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import os
import time
from typing import Any, Dict, List, Optional
import httpx
import jwt

from apps.api.config import get_settings
from apps.api.logger import logger


class GitHubAppError(Exception):
    """Base exception for GitHub App operations."""
    pass


class GitHubAppAuthError(GitHubAppError):
    """Raised when GitHub App or Installation credentials fail."""
    pass


class GitHubRepoNotFoundError(GitHubAppError):
    """Raised when a repository is not accessible under an installation."""
    pass


class GitHubAppService:
    """Manages GitHub App authentication, repository discovery, and webhook security."""

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        base_url: str = "https://api.github.com",
        http_client: Optional[httpx.AsyncClient] = None,
    ):
        self._app_id = app_id
        self._private_key = private_key
        self._webhook_secret = webhook_secret
        self.base_url = base_url.rstrip("/")
        self._custom_client = http_client
        # In-memory cache for installation access tokens: {installation_id: (token, expires_at_timestamp)}
        self._token_cache: Dict[int, tuple[str, float]] = {}

    @property
    def app_id(self) -> Optional[str]:
        return self._app_id or get_settings().GITHUB_APP_ID

    @property
    def private_key(self) -> Optional[str]:
        return self._private_key or get_settings().GITHUB_APP_PRIVATE_KEY

    @property
    def webhook_secret(self) -> Optional[str]:
        return self._webhook_secret or get_settings().GITHUB_WEBHOOK_SECRET

    def is_configured(self) -> bool:
        """Check if production GitHub App credentials are configured."""
        return bool(self.app_id and self.private_key)

    def generate_app_jwt(self) -> str:
        """Generate an RS256-signed JWT for the GitHub App."""
        if not self.is_configured():
            raise GitHubAppAuthError("GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY must be configured.")

        now = int(time.time())
        payload = {
            "iat": now - 60,       # 60 seconds in the past for clock drift
            "exp": now + (10 * 60), # 10 minutes maximum allowed by GitHub
            "iss": self.app_id,
        }

        # Normalize private key if escaped newlines were provided via env
        key_pem = self.private_key.replace("\\n", "\n")

        try:
            return jwt.encode(payload, key_pem, algorithm="RS256")
        except Exception as e:
            logger.error("Failed to sign GitHub App JWT", extra={"component": "github_app", "error": str(e)})
            raise GitHubAppAuthError(f"Failed to generate GitHub App JWT: {e}") from e

    def generate_install_url(self, workspace_id: str, state: str) -> str:
        """Generate the official GitHub App installation URL."""
        settings = get_settings()
        slug = settings.GITHUB_APP_SLUG or "devaura-repair"
        return f"https://github.com/apps/{slug}/installations/new?state={state}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._custom_client:
            return self._custom_client
        return httpx.AsyncClient(timeout=30.0)

    async def get_installation_access_token(self, installation_id: int) -> str:
        """Obtain a short-lived installation access token, with in-memory caching."""
        now = time.time()
        cached = self._token_cache.get(installation_id)
        if cached and cached[1] > (now + 120):  # Valid for at least 2 more minutes
            return cached[0]

        # In testing/unconfigured mode, if no private key is present, provide a mock token
        if not self.is_configured():
            mock_token = f"ghs_mock_token_inst_{installation_id}"
            self._token_cache[installation_id] = (mock_token, now + 3600)
            return mock_token

        app_jwt = self.generate_app_jwt()
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {app_jwt}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Devaura-Platform/1.0",
        }

        url = f"{self.base_url}/app/installations/{installation_id}/access_tokens"
        client = await self._get_client()
        try:
            res = await client.post(url, headers=headers)
            if res.status_code == 404:
                raise GitHubAppAuthError(f"GitHub App installation {installation_id} not found or access revoked.")
            if res.status_code != 201:
                raise GitHubAppAuthError(f"Failed to obtain installation token: HTTP {res.status_code}")

            data = res.json()
            token = data["token"]
            # Parse expires_at ISO string
            expires_at_dt = datetime.fromisoformat(data["expires_at"].replace("Z", "+00:00"))
            expires_at_ts = expires_at_dt.timestamp()

            self._token_cache[installation_id] = (token, expires_at_ts)
            return token
        finally:
            if not self._custom_client:
                await client.aclose()

    async def get_installation_repositories(self, installation_id: int) -> List[Dict[str, Any]]:
        """List repositories accessible to the GitHub App installation."""
        token = await self.get_installation_access_token(installation_id)

        # In test mode with mock token and no custom client, return deterministic repositories
        if token.startswith("ghs_mock_token_") and not self._custom_client:
            return [
                {
                    "id": 90123401,
                    "name": "payments-api",
                    "full_name": "acme-corp/payments-api",
                    "owner": {"login": "acme-corp", "id": 54321},
                    "private": True,
                    "default_branch": "main",
                    "permissions": {"admin": True, "push": True, "pull": True},
                },
                {
                    "id": 90123402,
                    "name": "frontend",
                    "full_name": "acme-corp/frontend",
                    "owner": {"login": "acme-corp", "id": 54321},
                    "private": False,
                    "default_branch": "main",
                    "permissions": {"admin": False, "push": True, "pull": True},
                },
                {
                    "id": 90123403,
                    "name": "checkout-service",
                    "full_name": "acme-corp/checkout-service",
                    "owner": {"login": "acme-corp", "id": 54321},
                    "private": True,
                    "default_branch": "main",
                    "permissions": {"admin": False, "push": True, "pull": True},
                },
            ]

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Devaura-Platform/1.0",
        }

        url = f"{self.base_url}/installation/repositories?per_page=100"
        client = await self._get_client()
        try:
            res = await client.get(url, headers=headers)
            if res.status_code != 200:
                raise GitHubAppError(f"Failed to list installation repositories: HTTP {res.status_code}")
            return res.json().get("repositories", [])
        finally:
            if not self._custom_client:
                await client.aclose()

    async def get_repository_details(
        self, installation_id: int, owner: str, repo: str
    ) -> Dict[str, Any]:
        """Fetch authoritative repository metadata from GitHub using the installation context."""
        token = await self.get_installation_access_token(installation_id)

        # In test mode with mock token and no custom client, return simulated repo metadata
        if token.startswith("ghs_mock_token_") and not self._custom_client:
            return {
                "id": 90123401,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "owner": {"login": owner, "id": 54321},
                "private": True,
                "default_branch": "main",
                "clone_url": f"https://github.com/{owner}/{repo}.git",
                "permissions": {"admin": True, "push": True, "pull": True},
            }

        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Devaura-Platform/1.0",
        }

        url = f"{self.base_url}/repos/{owner}/{repo}"
        client = await self._get_client()
        try:
            res = await client.get(url, headers=headers)
            if res.status_code == 404:
                raise GitHubRepoNotFoundError(
                    f"Repository '{owner}/{repo}' not found or not accessible to installation {installation_id}."
                )
            if res.status_code != 200:
                raise GitHubAppError(f"GitHub API error fetching repository: HTTP {res.status_code}")
            return res.json()
        finally:
            if not self._custom_client:
                await client.aclose()

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: Optional[str],
        secret: Optional[str] = None,
    ) -> bool:
        """Validate GitHub webhook HMAC-SHA256 signature against secret."""
        effective_secret = secret or self.webhook_secret
        if not effective_secret:
            # If no secret configured, fail verification closed
            logger.warning("Webhook received but GITHUB_WEBHOOK_SECRET is not configured. Rejecting.", extra={"component": "webhook"})
            return False

        if not signature_header or not signature_header.startswith("sha256="):
            return False

        expected_sig = signature_header.split("sha256=")[1].strip()
        computed_sig = hmac.new(
            effective_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_sig, computed_sig)


# Global singleton instance
_app_service: Optional[GitHubAppService] = None


def get_github_app_service() -> GitHubAppService:
    global _app_service
    if _app_service is None:
        _app_service = GitHubAppService()
    return _app_service
