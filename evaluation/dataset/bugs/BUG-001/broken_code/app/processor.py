def process_user_profile(user_dict):
    if user_dict is None:
        user_dict = {}
    profile = user_dict.get("profile")
    return profile.get("username", "anonymous")
