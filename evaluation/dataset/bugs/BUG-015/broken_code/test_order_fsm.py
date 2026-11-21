from app.order_fsm import can_transition

def test_valid_transition():
    assert can_transition("CREATED", "PROCESSING") is True

def test_terminal_cancelled():
    assert can_transition("CANCELLED", "COMPLETED") is False
