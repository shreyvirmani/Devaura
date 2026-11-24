from urllib3_util.url import parse_authority

def test_ipv6_authority_parsing():
    res = parse_authority('admin@[::1]:8080')
    assert res == ('admin', '[::1]', '8080')
