import re


FINAL_JUDGMENT_OPTIONS = [
    "미점검",
    "○ 합격",
    "X 불합격",
    "/ 해당없음",
    "미사용",
]

FINAL_PASS_VALUES = {"○ 합격", "적합", "○", "합격"}
FINAL_FAIL_VALUES = {"X 불합격", "조치필요", "부적합", "X", "불합격"}
FINAL_NA_VALUES = {"/ 해당없음", "해당없음", "/", "미사용"}

MEASUREMENT_KEYWORDS = (
    "유량", "풍량", "양정", "압력", "차압", "온도", "습도", "전류", "전압",
    "동력", "소음", "진동", "효율", "성능", "농도", "수질", "수위",
    "급기", "배기", "환기량", "열량", "냉방능력", "난방능력",
)


def normalize_final_judgment(value):
    text = str(value or "").strip()
    if text in FINAL_PASS_VALUES:
        return "○ 합격"
    if text in FINAL_FAIL_VALUES:
        return "X 불합격"
    if text in FINAL_NA_VALUES:
        return "/ 해당없음" if text != "미사용" else "미사용"
    if text == "미점검":
        return "미점검"
    return text or "미점검"


def is_final_pass(value):
    return normalize_final_judgment(value) == "○ 합격"


def is_final_fail(value):
    return normalize_final_judgment(value) == "X 불합격"


def is_final_na(value):
    return normalize_final_judgment(value) in {"/ 해당없음", "미사용"}


def is_measurement_item_data(item_data):
    source_text = " ".join([
        str(item_data.get("name", "")),
        str(item_data.get("method", "")),
        str(item_data.get("criteria", "")),
    ])
    return any(keyword in source_text for keyword in MEASUREMENT_KEYWORDS)


def parse_numeric_value(text):
    if text is None:
        return None
    value = str(text).replace(",", "").strip()
    if not value:
        return None
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", value)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def calculate_deviation(measured, design):
    if design is None or measured is None or design == 0:
        return None
    return (measured - design) / design * 100.0


def is_outside_tolerance(deviation, tolerance):
    return abs(deviation) > abs(tolerance)
