from app.client import get_formatted_user

def test_formatted_user():
    res = get_formatted_user({"uid": 42, "name": "Bob"})
    assert res == "User #42: Bob"
