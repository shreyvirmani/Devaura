class SessionStore:
    def __init__(self):
        self.sessions = {}

    def expire_session(self, sid):
        del self.sessions[sid]
