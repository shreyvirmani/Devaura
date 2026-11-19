"""Business service layer for user operations."""
from typing import Optional
from app.database import get_user, save_user
from app.models import User


class UserService:
    """Service handling high-level user workflows."""

    def __init__(self) -> None:
        self.active = True

    def process_user(self, user_id: str) -> Optional[User]:
        """Loads user via database.get_user and performs state update."""
        user = get_user(user_id)
        if user:
            user.save()
            save_user(user)
            return user
        return None

    def calculate_metrics(self, base_val: int) -> int:
        """Demonstrates nested function definition and invocation."""
        def inner_calc(val: int) -> int:
            return val * 2

        return inner_calc(base_val)
