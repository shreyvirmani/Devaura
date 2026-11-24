import os

def resolve_static_path(root_dir: str, rel_path: str) -> str:
    # Defect: Direct join without canonical prefix verification
    normalized = os.path.normpath(os.path.join(root_dir, rel_path.lstrip('/')))
    return normalized
