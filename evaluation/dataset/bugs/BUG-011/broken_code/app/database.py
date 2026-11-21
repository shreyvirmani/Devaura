DATABASE = {"u1": "Alice", "u2": "Bob"}

def query_record(record_id):
    return DATABASE.get(record_id)
