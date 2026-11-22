from pydantic_core.parser import parse_union_value
import pytest

def test_union_rejection_when_not_allowed():
    with pytest.raises(ValueError):
        parse_union_value(None, ['dict', 'int'])

def test_union_valid_value():
    assert parse_union_value({'a': 1}, ['dict', 'none']) == {'a': 1}
