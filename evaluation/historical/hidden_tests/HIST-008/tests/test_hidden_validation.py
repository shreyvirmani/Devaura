from tornado_http.chunk_parser import parse_chunk_size

def test_valid_chunk_size():
    assert parse_chunk_size('1a\r\n') == 26
