from app.webhook import route_webhook_event

def test_route_full_payload():
    assert route_webhook_event({"event": "payment", "status": "completed"}) == "payment:completed"

def test_route_missing_status():
    assert route_webhook_event({"event": "ping"}) == "ping:pending"
