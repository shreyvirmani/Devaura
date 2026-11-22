from app.database import get_user

def test_hidden_negative_id():
    assert get_user(-1) is None

def test_hidden_zero_id():
    assert get_user(0) is None

def test_hidden_second_user():
    assert get_user(2) == "Bob"
