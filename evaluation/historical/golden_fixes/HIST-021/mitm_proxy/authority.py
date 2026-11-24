def split_authority(authority: str) -> tuple:
    if not authority:
        raise ValueError('Empty authority string')
    host, sep, port_str = authority.rpartition(':')
    if not sep or not port_str:
        raise ValueError('Missing port in authority')
    return host, int(port_str)
