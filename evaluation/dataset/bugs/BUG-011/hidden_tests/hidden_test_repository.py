from app.repository import get_record

def test_hidden_second_user():
    assert get_record("u2") == "Bob"

def test_hidden_missing_user():
    assert get_record("u999") is None
