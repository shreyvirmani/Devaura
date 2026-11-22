from app.order_fsm import can_transition

def test_hidden_terminal_state():
    assert can_transition("CANCELLED", "PROCESSING") is False

def test_hidden_complete_flow():
    assert can_transition("PROCESSING", "COMPLETED") is True
