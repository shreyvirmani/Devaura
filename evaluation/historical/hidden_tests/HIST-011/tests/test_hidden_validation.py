from httpx_urls.urls import encode_query_params

def test_single_query_param():
    assert encode_query_params([('key', 'val')]) == 'key=val'

def test_mixed_query_params():
    assert encode_query_params([('a', '1'), ('b', '2'), ('a', '3')]) == 'a=1&b=2&a=3'
