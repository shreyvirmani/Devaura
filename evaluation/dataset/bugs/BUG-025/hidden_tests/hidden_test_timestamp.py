from app.time_helper import normalize_utc_timestamp

def test_hidden_offset_calculation():
    assert normalize_utc_timestamp(1600000000, 2) == 1600000000
