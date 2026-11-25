"""Devaura Durable Job Failure Classification & Retry Policy.

Explicitly classifies failures into retryable vs non-retryable while preserving
domain-specific failure classifications (quota exhaustion, GitHub, safety, etc.).
"""

from enum import Enum
import httpx


class FailureClassification(str, Enum):
    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"
    PROVIDER_QUOTA_EXHAUSTED = "PROVIDER_QUOTA_EXHAUSTED"
    REPAIR_FAILURE = "REPAIR_FAILURE"
    VERIFICATION_FAILURE = "VERIFICATION_FAILURE"
    CI_FAILURE = "CI_FAILURE"
    GITHUB_FAILURE = "GITHUB_FAILURE"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    INFORMATION_LEAKAGE = "INFORMATION_LEAKAGE"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"


class RetryableJobError(Exception):
    """Explicitly transient error eligible for bounded retry."""
    pass


class NonRetryableJobError(Exception):
    """Permanent error that must not be retried."""
    def __init__(self, message: str, classification: FailureClassification = FailureClassification.NON_RETRYABLE):
        super().__init__(message)
        self.classification = classification


class ProviderQuotaExhaustedError(Exception):
    """Explicit provider quota or rate-limit exhaustion."""
    pass


class SafetyBlockError(NonRetryableJobError):
    """Raised when a safety policy or protected-branch rule blocks execution."""
    def __init__(self, message: str):
        super().__init__(message, FailureClassification.SAFETY_BLOCK)


class GitHubFailureError(NonRetryableJobError):
    """Raised when GitHub API/git operations fail non-transiently."""
    def __init__(self, message: str):
        super().__init__(message, FailureClassification.GITHUB_FAILURE)


class VerificationFailureError(NonRetryableJobError):
    """Raised when sandbox verification fails."""
    def __init__(self, message: str):
        super().__init__(message, FailureClassification.VERIFICATION_FAILURE)


def is_retryable_classification(classification: FailureClassification) -> bool:
    return classification == FailureClassification.RETRYABLE


def classify_exception(exc: Exception) -> FailureClassification:
    """Classify an exception according to Devaura's explicit retry policy."""
    if isinstance(exc, ProviderQuotaExhaustedError):
        return FailureClassification.PROVIDER_QUOTA_EXHAUSTED

    if isinstance(exc, NonRetryableJobError):
        return exc.classification

    if isinstance(exc, RetryableJobError):
        return FailureClassification.RETRYABLE

    msg = str(exc).lower()

    # Provider quota / rate-limit signatures
    quota_terms = (
        "quota",
        "rate limit",
        "rate_limit",
        "resourceexhausted",
        "resource_exhausted",
        "429",
        "insufficient_quota",
    )
    if any(term in msg for term in quota_terms):
        return FailureClassification.PROVIDER_QUOTA_EXHAUSTED

    # Safety / leakage signatures
    if any(term in msg for term in ("safety policy", "protected branch", "self-approval", "path traversal")):
        return FailureClassification.SAFETY_BLOCK
    if "information boundary" in msg or "secret leakage" in msg:
        return FailureClassification.INFORMATION_LEAKAGE

    # Non-retryable domain/security errors
    if isinstance(exc, (ValueError, KeyError, PermissionError, TypeError)):
        return FailureClassification.NON_RETRYABLE

    non_retryable_terms = (
        "invalid repository",
        "authorization failure",
        "unauthorized",
        "forbidden",
        "malformed",
        "not found in this workspace",
        "access_revoked",
        "base revision",
        "hash mismatch",
    )
    if any(term in msg for term in non_retryable_terms):
        return FailureClassification.NON_RETRYABLE

    # Retryable network / timeout / transient errors
    if isinstance(exc, (TimeoutError, ConnectionError, OSError, httpx.TimeoutException, httpx.NetworkError)):
        return FailureClassification.RETRYABLE

    retryable_terms = (
        "timeout",
        "timed out",
        "temporarily unavailable",
        "connection reset",
        "502",
        "503",
        "504",
    )
    if any(term in msg for term in retryable_terms):
        return FailureClassification.RETRYABLE

    # Default unknown errors to NON_RETRYABLE to avoid blind infinite retries
    return FailureClassification.NON_RETRYABLE


def compute_backoff_seconds(attempt_count: int, base_seconds: int = 15, max_seconds: int = 300) -> int:
    """Compute bounded exponential backoff delay in seconds."""
    exponent = max(0, attempt_count - 1)
    return min(max_seconds, base_seconds * (2 ** exponent))
