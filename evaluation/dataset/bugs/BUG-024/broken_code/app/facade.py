from app.inventory import reserve_stock, STOCK

class OrderFacade:
    def place_order(self, item_id, count):
        reserve_stock(item_id, count)
        return STOCK.get(item_id)
