from botocore_auth.canonical import quote_v4_param

def test_alphanumeric():
    assert quote_v4_param('abcXYZ123') == 'abcXYZ123'

def test_space_encoded():
    assert quote_v4_param('hello world') == 'hello%20world'
