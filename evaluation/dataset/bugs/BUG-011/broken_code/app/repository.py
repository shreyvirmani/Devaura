from app.legacy_db import query_record

def get_record(record_id):
    return query_record(record_id)
