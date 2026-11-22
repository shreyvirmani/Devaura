from app.facade import OrderFacade

def test_hidden_facade_multiple_items():
    facade = OrderFacade()
    assert facade.place_order("item_2", 1) is not None
