from app.calculator import parse_and_multiply

def test_int():
    assert parse_and_multiply("4", 2) == 8

def test_float_string():
    assert parse_and_multiply("2.5", 2) == 5.0
