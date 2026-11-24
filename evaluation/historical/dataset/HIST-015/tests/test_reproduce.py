from lodash_util.merge import deep_merge

def test_prototype_pollution_blocked():
    payload = {'__proto__': {'admin': True}, 'name': 'test'}
    res = deep_merge({}, payload)
    assert '__proto__' not in res
    assert res.get('name') == 'test'
