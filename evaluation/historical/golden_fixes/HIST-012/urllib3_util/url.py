# Linear-time non-backtracking authority parser supporting IPv6
def parse_authority(authority: str):
    if not authority or len(authority) > 1024:
        raise ValueError('Invalid authority component')
    if '@' in authority:
        userinfo, _, host_port = authority.rpartition('@')
    else:
        userinfo, host_port = '', authority
    if ':' in host_port:
        host, _, port = host_port.rpartition(':')
    else:
        host, port = host_port, ''
    return (userinfo, host, port)
