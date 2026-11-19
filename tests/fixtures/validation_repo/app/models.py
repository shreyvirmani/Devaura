"""Data models for validation fixture repository."""
from typing import Dict, Any, Optional


class User:
    """Base user entity."""

    def __init__(self, user_id: str, username: str, email: str, role: str = "user") -> None:
        self.user_id = user_id
        self.username = username
        self.email = email
        self.role = role
        self.is_active = True

    def to_dict(self) -> Dict[str, Any]:
        """Serializes user to dictionary."""
        return {
            "id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
        }

    def save(self) -> bool:
        """Saves user record."""
        return True


class AdminUser(User):
    """Admin user extending base User with explicit permission management."""

    def __init__(self, user_id: str, username: str, email: str, permissions: Optional[list] = None) -> None:
        super().__init__(user_id, username, email, role="admin")
        self.permissions = permissions or ["read", "write", "delete", "admin"]

    def has_permission(self, perm: str) -> bool:
        """Checks if admin possesses the specified permission."""
        return perm in self.permissions


class GuestUser(User):
    """Guest user with read-only access."""

    def __init__(self, session_id: str) -> None:
        super().__init__(user_id=session_id, username="guest", email="guest@example.com", role="guest")
