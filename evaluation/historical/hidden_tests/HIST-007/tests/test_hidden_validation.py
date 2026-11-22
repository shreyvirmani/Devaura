from express_qs.parser import parse_nested_query

def test_constructor_pollution_defense():
    inp = {'constructor': {'prototype': {}}, 'q': '1'}
    out = parse_nested_query(inp)
    assert 'constructor' not in out
    assert out == {'q': '1'}
