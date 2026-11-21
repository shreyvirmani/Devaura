from app.serializer import serialize_user

def get_formatted_user(raw_user):
    s = serialize_user(raw_user)
    return f"User #{s['id']}: {s['name']}"
