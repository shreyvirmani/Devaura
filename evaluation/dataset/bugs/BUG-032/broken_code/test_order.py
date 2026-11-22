from app.order_processor import compute_item_total
from app.item_model import fetch_item_data

def test_order_with_dict():
    item = fetch_item_data("book", 15)
    assert compute_item_total(item, 2) == 30
