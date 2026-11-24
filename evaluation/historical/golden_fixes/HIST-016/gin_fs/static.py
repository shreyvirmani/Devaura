import os

def resolve_static_path(root_dir: str, rel_path: str) -> str:
    clean_root = os.path.abspath(root_dir)
    target = os.path.abspath(os.path.join(clean_root, rel_path.lstrip('/\\')))
    if not target.startswith(clean_root):
        raise PermissionError('Path traversal outside static root detected')
    return target
