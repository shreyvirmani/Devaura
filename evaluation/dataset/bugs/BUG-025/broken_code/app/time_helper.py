def normalize_utc_timestamp(epoch_seconds, offset_hours=0):
    return epoch_seconds + (offset_hours * 3600)
