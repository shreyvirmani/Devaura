from app.pagination import paginate_items

def test_hidden_page_exceeding_items():
    assert paginate_items([1, 2, 3], page=5, page_size=2) == []

def test_hidden_exact_page():
    assert paginate_items([1, 2, 3, 4], page=2, page_size=2) == [3, 4]
