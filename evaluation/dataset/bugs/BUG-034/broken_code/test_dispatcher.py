from app.dispatcher import ActionDispatcher

def test_dispatch_empty_refund():
    d = ActionDispatcher()
    assert d.dispatch("refund", {}) == 0
