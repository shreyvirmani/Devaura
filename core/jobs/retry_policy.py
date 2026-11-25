"""Devaura Durable Job Failure Classification & Retry Policy.

Explicitly classifies failures into:
- RETRYABLE: transient network/API/infra errors (eligible for bounded backoff)
- NON_RETRYABLE: invalid repo, auth failure, malformed input, policy violation
- PROVIDER_QUOTA_EXHAUSTED: explicit LLM/API quota exhaustion (never retried blindly)
"""

from enum import Enum
import httpx


class FailureClassification(str, Enum):
    RETRYABLE = "RETRYABLE"
    NON_RETRYABLE = "NON_RETRYABLE"
    PROVIDER_QUOTA_EXHAUSTED = "PROVIDER_QUOTA_EXHAUSTED"


class RetryableJobError(Exception):
    """Explicitly transient error eligible for bounded retry."""
    pass


class NonRetryableJobError(Exception):
    """Permanent error that must not be retried."""
    pass


class ProviderQuotaExhaustedError(Exception):
    """Explicit provider quota or rate-limit exhaustion."""
    pass


def classify_exception(exc: Exception) -> FailureClassification:
    """Classify an exception according to Devaura's explicit retry policy."""
    if isinstance(exc, ProviderQuotaExhaustedError):
        return FailureClassification.PROVIDER_QUOTA_EXHAUSTED

    if isinstance(exc, NonRetryableJobError):
        return FailureClassification.NON_RETRYABLE

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

    # Non-retryable domain/security errors
    if isinstance(exc, (ValueError, KeyError, PermissionError, TypeError)):
        return FailureClassification.NON_RETRYABLE

    non_retryable_terms = (
        "invalid repository",
        "authorization failure",
        "unauthorized",
        "forbidden",
        "malformed",
        "safety policy",
        "information boundary",
        "not found in this workspace",
        "access_revoked",
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
