from app.http_service import get_request_timeout

def test_hidden_timeout_value():
    assert get_request_timeout() == 30
