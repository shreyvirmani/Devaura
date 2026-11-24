from lodash_util.merge import deep_merge

def test_constructor_blocked():
    payload = {'constructor': {'prototype': {}}, 'valid': 123}
    res = deep_merge({}, payload)
    assert 'constructor' not in res
    assert res == {'valid': 123}
