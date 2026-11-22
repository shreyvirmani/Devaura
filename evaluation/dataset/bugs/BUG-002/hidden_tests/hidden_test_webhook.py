from app.webhook import route_webhook_event

def test_hidden_failed_status():
    assert route_webhook_event({"event": "order", "status": "failed"}) == "order:failed"

def test_hidden_empty_payload():
    assert route_webhook_event({}) == "unknown:pending"
