from app.models import make_record
from app.repo import get_record_timestamp

def test_get_timestamp():
    r = make_record("r1", 1700000000)
    assert get_record_timestamp(r) == 1700000000
