from app.database import get_user

def test_get_existing_user():
    assert get_user(1) == "Alice"

def test_get_missing_user():
    assert get_user(99) is None
