def deserialize_string_list(values: list, allow_none_element: bool = False) -> list:
    # Defect: Unchecked call to item.strip() when item is None
    return [item.strip() for item in values]
