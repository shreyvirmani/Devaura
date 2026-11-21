from app.time_helper import normalize_utc_timestamp

def test_zero_offset():
    assert normalize_utc_timestamp(1700000000, 0) == 1700000000

def test_normalize_strips_offset():
    assert normalize_utc_timestamp(1700000000, 5) == 1700000000
