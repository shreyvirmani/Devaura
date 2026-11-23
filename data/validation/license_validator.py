"""Devaura Real Data Pipeline: License Validation.

Enforces that all ingested repositories and defect records carry valid, permissive
open-source licenses permitting analysis, benchmarking, and machine learning evaluation.
"""

from typing import Set

# Permissive and recognized open-source licenses approved for dataset inclusion
APPROVED_OPEN_SOURCE_LICENSES: Set[str] = {
    "MIT",
    "APACHE-2.0",
    "APACHE 2.0",
    "BSD-3-CLAUSE",
    "BSD 3-CLAUSE",
    "BSD-2-CLAUSE",
    "BSD 2-CLAUSE",
    "ISC",
    "PYTHON-2.0",
    "PSF",
    "PSFL",
    "MPL-2.0",
    "UNLICENSE",
    "CC0-1.0",
    "0BSD",
}

FORBIDDEN_LICENSES: Set[str] = {
    "PROPRIETARY",
    "ALL RIGHTS RESERVED",
    "UNKNOWN",
    "COMMERCIAL",
    "NONE",
}


class LicenseValidationError(ValueError):
    """Raised when an ingested artifact violates open-source licensing requirements."""
    pass


class LicenseValidator:
    """Validates license compatibility for real-world software defect datasets."""

    @classmethod
    def is_permissive(cls, license_name: str) -> bool:
        """Check if a license string conforms to approved open-source licenses."""
        if not license_name or not isinstance(license_name, str):
            return False
        normalized = license_name.strip().upper()
        if normalized in FORBIDDEN_LICENSES:
            return False
        # Direct match or substring match for variants (e.g. "MIT License")
        for approved in APPROVED_OPEN_SOURCE_LICENSES:
            if approved in normalized or normalized in approved:
                return True
        return False

    @classmethod
    def validate_license(cls, repository: str, license_name: str) -> None:
        """Enforces permissible license, raising LicenseValidationError if incompatible."""
        if not cls.is_permissive(license_name):
            raise LicenseValidationError(
                f"Repository '{repository}' has unapproved or non-permissive license '{license_name}'. "
                f"Devaura requires approved open-source licensing ({', '.join(sorted(APPROVED_OPEN_SOURCE_LICENSES))})."
            )
