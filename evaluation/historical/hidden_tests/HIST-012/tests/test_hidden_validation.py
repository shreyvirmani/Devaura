from urllib3_util.url import parse_authority

def test_standard_authority():
    res = parse_authority('user:pass@localhost:8080')
    assert res == ('user:pass', 'localhost', '8080')

def test_simple_host():
    res = parse_authority('localhost')
    assert res == ('', 'localhost', '')
