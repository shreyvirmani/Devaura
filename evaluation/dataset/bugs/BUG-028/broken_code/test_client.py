from app.client import send_request

def test_send():
    assert send_request("secret_key_123") == "secret_key_123"
