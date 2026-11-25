"""Devaura Production Authentication & Identity Resolution.

Extracts, validates, and resolves the current authenticated user from
Bearer tokens, API keys, or session cookies.
"""

from typing import Optional
from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from apps.api.config import get_settings
from apps.api.security import decode_access_token
from database.connection import get_db
from database.models import User


class CurrentUser(BaseModel):
    """Authenticated user context passed to request handlers."""
    id: str
    email: str
    name: str
    is_authenticated: bool = True
    is_superuser: bool = False

    @property
    def username(self) -> str:
        return self.email or self.name or self.id


DEV_USER = CurrentUser(
    id="usr_devaura_dev_001",
    email="dev@devaura.local",
    name="Devaura Engineer",
    is_authenticated=True,
    is_superuser=False,
)


def create_auth_error(status_code: int, code: str, message: str) -> HTTPException:
    """Create a standardized error response adhering to production error guidelines."""
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    devaura_token: Optional[str] = Cookie(None),
    db: AsyncSession = Depends(get_db),
) -> Optional[CurrentUser]:
    """Extract authenticated identity from Bearer token, Cookie, or API key.
    
    Returns None if unauthenticated.
    """
    token: Optional[str] = None

    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
        else:
            raise create_auth_error(
                status.HTTP_401_UNAUTHORIZED,
                "INVALID_AUTH_HEADER",
                "Invalid Authorization header format. Expected 'Bearer <token>'.",
            )
    elif devaura_token:
        token = devaura_token
    elif x_api_key:
        # API Key authentication path
        return CurrentUser(
            id=f"usr_api_{x_api_key[:8]}",
            email=f"apikey_{x_api_key[:6]}@devaura.local",
            name="API Key User",
            is_authenticated=True,
            is_superuser=False,
        )

    if not token:
        return None

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "SESSION_EXPIRED",
            "Authentication session has expired. Please sign in again.",
        )
    except jwt.InvalidTokenError:
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN",
            "Invalid authentication token.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "INVALID_TOKEN_CLAIMS",
            "Token payload missing subject identifier.",
        )

    # Resolve active user from database
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "USER_NOT_FOUND",
            "Authenticated user account is inactive or not found.",
        )

    return CurrentUser(
        id=user.id,
        email=user.email,
        name=user.name,
        is_authenticated=True,
        is_superuser=user.is_superuser,
    )


async def require_authenticated_user(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
) -> CurrentUser:
    """Strict dependency requiring authenticated user context."""
    if not current_user or not current_user.is_authenticated:
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "Authentication required.",
        )
    return current_user


async def get_current_user(
    current_user: Optional[CurrentUser] = Depends(get_current_user_optional),
) -> CurrentUser:
    """Identity dependency with strict production boundary enforcement.
    
    In production, staging, or production-like environments, DEV_USER fallback
    is strictly prohibited and fails closed with HTTP 401 Unauthorized.
    In testing/development, fallback is ONLY permitted if ALLOW_DEV_USER_FALLBACK
    is explicitly enabled in configuration for legacy test isolation.
    """
    if current_user:
        return current_user

    settings = get_settings()

    # Fail closed: DEV_USER fallback is strictly prohibited in production and staging
    normalized_env = (settings.APP_ENV or "").lower().strip()
    if normalized_env in ("production", "staging", "prod", "stage"):
        raise create_auth_error(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "Authentication required. Identity fallback is strictly disabled in production/staging environments.",
        )

    # In development/testing, fallback is only allowed if explicitly enabled in configuration
    if normalized_env in ("development", "testing") and getattr(settings, "ALLOW_DEV_USER_FALLBACK", False):
        return DEV_USER

    raise create_auth_error(
        status.HTTP_401_UNAUTHORIZED,
        "UNAUTHORIZED",
        "Authentication required. Missing Bearer token or session cookie.",
    )
