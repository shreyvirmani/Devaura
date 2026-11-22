from app.session_store import SessionStore

def test_cache_invalidation_after_logout():
    store = SessionStore()
    store.sessions["s1"] = {"user": "alice"}
    store.expire_session("s1")
    # Idempotent second call
    store.expire_session("s1")
