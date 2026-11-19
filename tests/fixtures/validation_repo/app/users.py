"""User management module with deliberate same-name symbol cases."""
from typing import Optional
from app.database import save_user
from app.models import AdminUser, User


def get_user(user_id: str) -> Optional[User]:
    """User-facing lookup function with same name as database.get_user."""
    user = User(user_id=user_id, username=f"profile_{user_id}", email=f"{user_id}@users.local")
    return user


def create_user(user_id: str, username: str, email: str, is_admin: bool = False) -> User:
    """Creates and persists new user or admin."""
    if is_admin:
        new_user = AdminUser(user_id=user_id, username=username, email=email)
    else:
        new_user = User(user_id=user_id, username=username, email=email)

    save_user(new_user)
    return new_user
