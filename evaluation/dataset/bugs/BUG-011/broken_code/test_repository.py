from app.repository import get_record

def test_get_existing():
    assert get_record("u1") == "Alice"
