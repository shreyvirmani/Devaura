from app.http_service import get_request_timeout

def test_default_timeout():
    assert get_request_timeout() == 30

def test_override_timeout():
    assert get_request_timeout(10) == 10
