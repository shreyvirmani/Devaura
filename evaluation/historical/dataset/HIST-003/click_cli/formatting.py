def format_command_path(parts: list) -> str:
    # Defect: Direct join without string coercion
    return ' '.join(parts)
