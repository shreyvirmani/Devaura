def safe_lookup(obj: dict, attr: str):
    # Defect: Only checks attr == '__class__', allowing __globals__ and __subclasses__
    if attr == '__class__':
        raise PermissionError("Access to '__class__' is forbidden")
    return obj.get(attr)
