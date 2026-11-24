from axios_params.serializer import serialize_params

def test_scalar_param():
    assert serialize_params({'page': 1}) == 'page=1'

def test_empty_params():
    assert serialize_params({}) == ''
