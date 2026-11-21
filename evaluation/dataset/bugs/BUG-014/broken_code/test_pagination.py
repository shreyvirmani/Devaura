from app.pagination import paginate_items

def test_page_size_three():
    data = [1, 2, 3, 4, 5, 6]
    assert paginate_items(data, page=1, page_size=3) == [1, 2, 3]
    assert paginate_items(data, page=2, page_size=3) == [4, 5, 6]
