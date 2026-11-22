from app.processor import process_user_profile

def test_hidden_empty_dict():
    assert process_user_profile({}) == "anonymous"

def test_hidden_custom_name():
    assert process_user_profile({"profile": {"username": "bob"}}) == "bob"

def test_hidden_none_user():
    assert process_user_profile(None) == "anonymous"
