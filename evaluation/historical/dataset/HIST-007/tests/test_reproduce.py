from express_qs.parser import parse_nested_query

def test_proto_pollution_defense():
    inp = {'__proto__': {'polluted': True}, 'user': 'alice'}
    out = parse_nested_query(inp)
    assert '__proto__' not in out
    assert out.get('user') == 'alice'
