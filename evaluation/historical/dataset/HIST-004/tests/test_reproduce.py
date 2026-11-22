from pydantic_core.parser import parse_union_value

def test_union_optional_parsing():
    assert parse_union_value(None, ['dict', 'none']) is None
