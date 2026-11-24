import urllib.parse

def quote_v4_param(val: str) -> str:
    return urllib.parse.quote(val, safe='-_.~')
