def split_authority(authority: str) -> tuple:
    # Defect: Simple split on colon breaks on IPv6 bracketed colons
    parts = authority.split(':')
    if len(parts) != 2:
        raise ValueError('Too many colon segments in authority')
    return parts[0], int(parts[1])
