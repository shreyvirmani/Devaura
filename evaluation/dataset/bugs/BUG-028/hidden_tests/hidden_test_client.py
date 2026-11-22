from app.client import send_request

def test_hidden_empty_key():
    assert send_request("") == ""

def test_hidden_special_chars():
    assert send_request("key_!@#") == "key_!@#"
