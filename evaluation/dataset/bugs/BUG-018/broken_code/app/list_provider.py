TAG_DATA = {"v1": True, "v2": False, "v3": True}

def get_active_tags():
    return {k: v for k, v in TAG_DATA.items() if v}
