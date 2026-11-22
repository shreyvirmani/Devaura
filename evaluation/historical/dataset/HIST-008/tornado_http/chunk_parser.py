def parse_chunk_size(chunk_line: str) -> int:
    # Defect: Insecurely uses strip() allowing tabs and arbitrary whitespace
    cleaned = chunk_line.strip()
    return int(cleaned, 16)
