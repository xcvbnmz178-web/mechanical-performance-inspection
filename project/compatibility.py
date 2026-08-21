def normalize_legacy_judgments(inspection_results, normalize_judgment):
    for _key, _rows in inspection_results.items():
        if not isinstance(_rows, list):
            continue
        for _item in _rows:
            if isinstance(_item, dict):
                _item["판정"] = normalize_judgment(
                    _item.get("판정", "미점검")
                )
    return inspection_results
