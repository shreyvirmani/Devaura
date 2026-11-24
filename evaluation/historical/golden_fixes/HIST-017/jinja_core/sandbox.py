def safe_lookup(obj: dict, attr: str):
    if attr.startswith('_') or attr in ('__class__', '__globals__', '__subclasses__', '__bases__'):
        raise PermissionError(f"Access to private attribute '{attr}' is forbidden")
    return obj.get(attr)
