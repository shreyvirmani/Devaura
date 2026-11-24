from serde_types.uint import parse_uint64

def test_u64_deserialization():
    val = 0xFFFFFFFFFFFFFFFF
    assert parse_uint64(val) == 18446744073709551615
