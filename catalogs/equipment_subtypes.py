"""Stable subtype codes and properties for chiller equipment only."""


CHILLER_SUBTYPES = (
    {
        "code": "unspecified",
        "label": "미지정",
        "electric_compression": False,
        "absorption": False,
        "combustion": None,
    },
    {
        "code": "turbo",
        "label": "터보냉동기",
        "electric_compression": True,
        "absorption": False,
        "combustion": False,
    },
    {
        "code": "screw",
        "label": "스크류냉동기",
        "electric_compression": True,
        "absorption": False,
        "combustion": False,
    },
    {
        "code": "reciprocating",
        "label": "왕복동냉동기",
        "electric_compression": True,
        "absorption": False,
        "combustion": False,
    },
    {
        "code": "other_compression",
        "label": "기타 압축식 냉동기",
        "electric_compression": True,
        "absorption": False,
        "combustion": False,
    },
    {
        "code": "absorption",
        "label": "흡수식 냉동기",
        "electric_compression": False,
        "absorption": True,
        # 내부 데이터만으로 열원과 연소 여부를 확정하지 않는다.
        "combustion": None,
    },
    {
        "code": "direct_fired_absorption",
        "label": "직화식 흡수냉온수기",
        "electric_compression": False,
        "absorption": True,
        "combustion": True,
    },
)


_CHILLER_SUBTYPE_BY_CODE = {
    item["code"]: item for item in CHILLER_SUBTYPES
}
_CHILLER_SUBTYPE_CODE_BY_LABEL = {
    item["label"]: item["code"] for item in CHILLER_SUBTYPES
}


def normalize_chiller_subtype(value):
    text = str(value or "").strip()
    if text in _CHILLER_SUBTYPE_BY_CODE:
        return text
    return _CHILLER_SUBTYPE_CODE_BY_LABEL.get(text, "unspecified")


def chiller_subtype_info(value):
    code = normalize_chiller_subtype(value)
    return dict(_CHILLER_SUBTYPE_BY_CODE[code])


def is_chiller_electric_compression(value):
    return chiller_subtype_info(value)["electric_compression"]


def is_chiller_absorption(value):
    return chiller_subtype_info(value)["absorption"]


def is_chiller_combustion(value):
    """Return True, False, or None when combustion is not determined."""
    return chiller_subtype_info(value)["combustion"]
