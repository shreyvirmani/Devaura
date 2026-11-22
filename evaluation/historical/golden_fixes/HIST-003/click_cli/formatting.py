def format_command_path(parts: list) -> str:
    str_parts = [p.decode('utf-8', 'replace') if isinstance(p, (bytes, bytearray)) else str(p) for p in parts]
    return ' '.join(str_parts)
