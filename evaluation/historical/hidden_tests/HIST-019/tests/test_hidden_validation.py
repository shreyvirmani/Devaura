from serde_types.uint import parse_uint64
import pytest

def test_zero_uint64():
    assert parse_uint64(0) == 0

def test_negative_uint64():
    with pytest.raises(OverflowError):
        parse_uint64(-1)
