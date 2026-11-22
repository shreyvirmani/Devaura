def query_user(uid):
    return None if uid <= 0 else {"id": uid, "name": f"User_{uid}"}
