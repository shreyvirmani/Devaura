import urllib.parse

def quote_v4_param(val: str) -> str:
    # Defect: Replaces ~ with %7E for legacy compatibility contrary to SigV4 spec
    quoted = urllib.parse.quote(val, safe='-_.~')
    return quoted.replace('~', '%7E')
