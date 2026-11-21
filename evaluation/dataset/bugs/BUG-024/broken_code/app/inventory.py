STOCK = {"item_1": 10}

def reserve_stock(item_id, count):
    current = STOCK.get(item_id, 0)
    STOCK[item_id] = current + count
    return True
