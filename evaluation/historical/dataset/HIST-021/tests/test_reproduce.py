from mitm_proxy.authority import split_authority

def test_ipv6_connect_authority():
    host, port = split_authority('[2001:db8::1]:8080')
    assert host == '[2001:db8::1]'
    assert port == 8080
