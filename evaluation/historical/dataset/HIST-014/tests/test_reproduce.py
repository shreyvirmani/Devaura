from axios_params.serializer import serialize_params

def test_array_param_serialization():
    res = serialize_params({'tags': ['alpha', 'beta']})
    assert res == 'tags[]=alpha&tags[]=beta'
