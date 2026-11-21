from app.facade import OrderFacade

def test_order_facade_placement():
    facade = OrderFacade()
    rem = facade.place_order("item_1", 2)
    assert rem == 8
