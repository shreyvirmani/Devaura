import re

# Defect: Regex cannot parse IPv6 bracketed colons
AUTHORITY_RE = re.compile(r'^([^@:]+(:[^@]+)?@)?([^:]+)(:([0-9]+))?$')

def parse_authority(authority: str):
    match = AUTHORITY_RE.match(authority)
    if not match:
        raise ValueError('Invalid authority component')
    userinfo = (match.group(1) or '').rstrip('@')
    host = match.group(3)
    port = (match.group(5) or '')
    return (userinfo, host, port)
