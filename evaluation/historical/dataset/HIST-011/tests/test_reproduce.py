from httpx_urls.urls import encode_query_params

def test_duplicate_query_params():
    params = [('filter', 'a'), ('filter', 'b')]
    assert encode_query_params(params) == 'filter=a&filter=b'
