from app.db_layer import query_user

def get_user_view(uid):
    u = query_user(uid)
    return {"status": 200, "user_id": u["id"]}
