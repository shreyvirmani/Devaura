from guava_stream.limit import check_stream_bounds

def test_stream_limit_bounds():
    assert check_stream_bounds(9223372036854775800, 100, 1000) is False
