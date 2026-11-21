from app.processor import process_user_profile

def test_process_valid_user():
    assert process_user_profile({"profile": {"username": "alice"}}) == "alice"

def test_process_none_profile():
    assert process_user_profile({"profile": None}) == "anonymous"

def test_process_missing_profile():
    assert process_user_profile({}) == "anonymous"
