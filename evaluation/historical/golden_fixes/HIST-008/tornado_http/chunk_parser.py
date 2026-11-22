def parse_chunk_size(chunk_line: str) -> int:
    if not chunk_line.endswith('\r\n'):
        raise ValueError('Chunk line must end with CRLF')
    token = chunk_line[:-2]
    if ' ' in token or '\t' in token:
        raise ValueError('Invalid chunk size header contains whitespace')
    return int(token, 16)
