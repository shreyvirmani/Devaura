def serialize_user(raw_user):
    return {
        "user_id": raw_user["uid"],
        "name": raw_user["name"],
    }
