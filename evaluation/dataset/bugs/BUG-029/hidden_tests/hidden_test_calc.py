from app.calculator import parse_and_multiply

def test_hidden_zero():
    assert parse_and_multiply("0.0", 5) == 0.0

def test_hidden_negative():
    assert parse_and_multiply("-3.5", 2) == -7.0
