"""Devaura Security & Cryptographic Utilities.

Implements PBKDF2-HMAC-SHA256 password hashing (NIST SP 800-63B compliant)
and PyJWT token generation and verification.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from typing import Any, Dict, Optional
import jwt
from apps.api.config import get_settings


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, iterations: int = 600000) -> str:
    """Hash a plaintext password with a random 32-byte salt using PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return f"pbkdf2:sha256:{iterations}${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    try:
        header, salt, stored_key = hashed_password.split("$")
        algorithm, iterations_str = header.split(":")[-2:]
        iterations = int(iterations_str)

        computed_key = hashlib.pbkdf2_hmac(
            algorithm,
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(computed_key.hex(), stored_key)
    except Exception:
        return False


def create_access_token(
    subject: str,
    email: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[Dict[str, Any]] = None,
) -> str:
    """Create a signed JWT access token."""
    settings = get_settings()
    now = utc_now()
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(hours=24)

    payload = {
        "sub": subject,
        "email": email,
        "iat": now,
        "exp": expire,
        "nbf": now,
        "iss": "devaura-auth",
    }
    if extra_claims:
        payload.update(extra_claims)

    encoded_jwt = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT access token.
    
    Raises:
        jwt.ExpiredSignatureError: When token has expired.
        jwt.InvalidTokenError: When signature or claims are invalid.
    """
    settings = get_settings()
    decoded = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],
        issuer="devaura-auth",
        options={"require": ["sub", "exp", "iat"]},
    )
    return decoded
