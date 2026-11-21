def route_webhook_event(payload):
    event_type = payload.get("event", "unknown")
    status = payload["status"]
    return f"{event_type}:{status}"
