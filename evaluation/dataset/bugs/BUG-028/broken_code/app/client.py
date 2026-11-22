from app.auth_header import make_headers

def send_request(key):
    headers = make_headers(key)
    return headers["authorization"]
