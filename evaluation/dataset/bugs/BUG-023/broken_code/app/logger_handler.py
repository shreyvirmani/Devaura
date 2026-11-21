def handle_error(action_fn):
    try:
        return action_fn()
    except Exception as err:
        return f"Error: {err_log}"
