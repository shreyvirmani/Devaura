from app.models import make_record
from app.repo import get_record_timestamp

def test_hidden_record_timestamp():
    r = make_record("test_rec", 1600000000)
    assert get_record_timestamp(r) == 1600000000
