class ActionDispatcher:
    def dispatch(self, action, payload):
        fn = getattr(self, f"on_{action}", None)
        if not fn:
            raise NotImplementedError(f"Action '{action}' not implemented")
        return fn(payload)

    def on_refund(self, payload):
        return payload["amount"]
