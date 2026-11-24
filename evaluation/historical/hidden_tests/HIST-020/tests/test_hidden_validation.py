from guava_stream.limit import check_stream_bounds

def test_valid_bounds():
    assert check_stream_bounds(10, 20, 100) is True

def test_exact_limit():
    assert check_stream_bounds(50, 50, 100) is True
