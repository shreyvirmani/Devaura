"""Authentication and authorization services with deliberate test cases."""
import functools
import hashlib
from typing import Any, Callable, Optional
from app.database import get_user as fetch_db_user
from app.models import User

# Deliberate unresolved import to validate graceful unresolved handling
try:
    from unknown_module import missing_helper
except ImportError:
    missing_helper = None


def auth_required(func: Callable) -> Callable:
    """Decorator verifying authenticated user."""
    @functools.wraps(func)
    def wrapper(user_id: str, *args, **kwargs):
        user = fetch_db_user(user_id)
        if not user or not user.is_active:
            raise PermissionError("User is unauthorized or inactive")
        return func(user_id, *args, **kwargs)
    return wrapper


def hash_password(raw_password: str) -> str:
    """Computes SHA-256 hash of password."""
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def verify_password(raw_password: str, hashed: str) -> bool:
    """Verifies raw password matches hash via direct call to hash_password."""
    computed = hash_password(raw_password)
    return computed == hashed


async def authenticate(username: str, password_hash: str) -> Optional[User]:
    """Asynchronously authenticates user by id using aliased import."""
    user = fetch_db_user(username)
    if user and user.is_active:
        return user
    return None


def dynamic_dispatch(user: User, action_name: str) -> Any:
    """Demonstrates dynamic call via getattr for unresolved static analysis verification."""
    method = getattr(user, action_name, None)
    if callable(method):
        return method()
    return None
