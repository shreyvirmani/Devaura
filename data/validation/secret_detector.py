"""Devaura Real Data Pipeline: Secret and Credential Detection.

Scans ingested source code, issues, diffs, and commits for leaked credentials,
API keys, tokens, or private keys before storage in real-world datasets.
"""

import re
from typing import Dict, List, Tuple


class SecretDetectedError(ValueError):
    """Raised when an unredacted secret is detected in ingested data."""
    pass


class SecretDetector:
    """Detects and redacts credentials across ingested dataset records."""

    PATTERNS: Dict[str, re.Pattern] = {
        "GITHUB_TOKEN": re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{20,255}"),
        "GITHUB_FINE_GRAINED": re.compile(r"github_pat_[A-Za-z0-9_]{30,128}"),
        "GOOGLE_API_KEY": re.compile(r"AIza[0-9A-Za-z-_]{20,64}"),
        "OPENAI_KEY": re.compile(r"sk-[A-Za-z0-9]{20,64}"),
        "OPENAI_PROJECT_KEY": re.compile(r"sk-proj-[A-Za-z0-9_-]{20,128}"),
        "ANTHROPIC_KEY": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,128}"),
        "AWS_KEY_ID": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "PRIVATE_KEY": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
        "GENERIC_SECRET_ASSIGNMENT": re.compile(
            r'(?:api_key|access_token|secret_key|auth_token)\s*=\s*["\']([a-zA-Z0-9_\-]{20,})["\']',
            re.IGNORECASE,
        ),
    }

    @classmethod
    def find_secrets(cls, text: str) -> List[Tuple[str, str]]:
        """Identify any potential secrets in the provided text.
        
        Returns list of (pattern_name, matched_preview).
        """
        if not text or not isinstance(text, str):
            return []
        findings: List[Tuple[str, str]] = []
        for name, pattern in cls.PATTERNS.items():
            matches = pattern.findall(text)
            for m in matches:
                # If tuple from group match
                match_str = m if isinstance(m, str) else m[0]
                preview = match_str[:6] + "..." + match_str[-4:] if len(match_str) > 12 else match_str[:4] + "..."
                findings.append((name, preview))
        return findings

    @classmethod
    def assert_clean(cls, context_label: str, text: str) -> None:
        """Enforces that text contains zero secrets, raising SecretDetectedError if found."""
        findings = cls.find_secrets(text)
        if findings:
            details = ", ".join(f"{name} ({preview})" for name, preview in findings)
            raise SecretDetectedError(
                f"Secret detected in '{context_label}': {details}. Ingestion aborted."
            )

    @classmethod
    def sanitize(cls, text: str) -> str:
        """Scrub all recognized secrets with [REDACTED_SECRET]."""
        if not text:
            return ""
        sanitized = text
        for pattern in cls.PATTERNS.values():
            sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)
        return sanitized
