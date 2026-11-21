from app.calendar_util import is_leap_year

def test_standard_leap_year():
    assert is_leap_year(2024) is True

def test_century_not_divisible_by_400():
    assert is_leap_year(1900) is False

def test_century_divisible_by_400():
    assert is_leap_year(2000) is True
