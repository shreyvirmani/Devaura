from app.dispatcher import ActionDispatcher

def test_hidden_valid_refund():
    d = ActionDispatcher()
    assert d.dispatch("refund", {"amount": 75}) == 75

def test_hidden_none_payload():
    d = ActionDispatcher()
    assert d.dispatch("refund", None) == 0
