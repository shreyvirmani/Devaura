from botocore_auth.canonical import quote_v4_param

def test_sigv4_tilde_preserved():
    assert quote_v4_param('user~name') == 'user~name'
