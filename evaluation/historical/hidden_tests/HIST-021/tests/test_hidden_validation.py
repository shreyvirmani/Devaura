from mitm_proxy.authority import split_authority

def test_ipv4_authority():
    host, port = split_authority('127.0.0.1:443')
    assert host == '127.0.0.1'
    assert port == 443

def test_domain_authority():
    host, port = split_authority('example.com:80')
    assert host == 'example.com'
    assert port == 80
