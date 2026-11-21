def hash_auth_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
