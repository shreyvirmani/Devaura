from app.calendar_util import is_leap_year

def test_hidden_year_2000():
    assert is_leap_year(2000) is True

def test_hidden_year_1900():
    assert is_leap_year(1900) is False

def test_hidden_year_2028():
    assert is_leap_year(2028) is True
