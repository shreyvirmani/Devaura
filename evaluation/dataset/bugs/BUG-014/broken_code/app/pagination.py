def paginate_items(items, page, page_size):
    start = (page - 1) * page_size
    end = start + page_size - 1
    return items[start:end]
