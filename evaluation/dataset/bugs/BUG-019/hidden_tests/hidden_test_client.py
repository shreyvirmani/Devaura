from app.client import get_formatted_user

def test_hidden_another_user():
    res = get_formatted_user({"uid": 99, "name": "Alice"})
    assert res == "User #99: Alice"
