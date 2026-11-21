ALLOWED_TRANSITIONS = {
    "CREATED": ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["COMPLETED", "CANCELLED"],
    "CANCELLED": ["COMPLETED"],
    "COMPLETED": []
}

def can_transition(current, target):
    return target in ALLOWED_TRANSITIONS.get(current, [])
