from tornado_http.chunk_parser import parse_chunk_size
import pytest

def test_reject_whitespace_chunk_header():
    with pytest.raises(ValueError):
        parse_chunk_size('10 \t\r\n')
