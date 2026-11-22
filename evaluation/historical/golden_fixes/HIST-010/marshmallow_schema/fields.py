def deserialize_string_list(values: list, allow_none_element: bool = False) -> list:
    res = []
    for item in values:
        if item is None:
            if not allow_none_element:
                raise ValueError('None elements not permitted')
            res.append(None)
        else:
            res.append(str(item).strip())
    return res
