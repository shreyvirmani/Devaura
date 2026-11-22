from app.session_store import SessionStore

def test_hidden_empty_store():
    store = SessionStore()
    store.expire_session("nonexistent")
    assert store.sessions == {}

def test_hidden_multiple_sessions():
    store = SessionStore()
    store.sessions["s1"] = 1
    store.sessions["s2"] = 2
    store.expire_session("s1")
    assert "s2" in store.sessions
