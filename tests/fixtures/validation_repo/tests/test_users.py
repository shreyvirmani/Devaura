import pytest
from app.users import create_user, get_user


def test_create_user():
    u = create_user("u1", "alice", "alice@example.com", is_admin=False)
    assert u.username == "alice"
    assert u.role == "user"


def test_get_user():
    u = get_user("u1")
    assert u is not None
    assert u.user_id == "u1"
