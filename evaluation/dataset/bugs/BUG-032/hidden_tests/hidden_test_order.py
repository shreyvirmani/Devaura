from app.order_processor import compute_item_total

class MockItem:
    def __init__(self, price):
        self.price = price

def test_hidden_object_support():
    assert compute_item_total(MockItem(20), 3) == 60

def test_hidden_zero_qty():
    assert compute_item_total({"price": 50}, 0) == 0
