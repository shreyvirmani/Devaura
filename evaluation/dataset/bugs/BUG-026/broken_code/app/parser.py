def extract_token(raw_input):
    if not raw_input or "token=" not in raw_input:
        return None
    return raw_input.split("token=")[1].split(";")[0]
