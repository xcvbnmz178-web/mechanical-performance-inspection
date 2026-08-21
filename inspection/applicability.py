"""Pure applicability rules for chiller inspection items.

These rules describe whether an inspection item is relevant to a selected
chiller subtype.  They do not alter final judgments, technical reviews, UI
visibility, or saved project data.
"""

from catalogs.equipment_subtypes import normalize_chiller_subtype


APPLICABLE = "applicable"
NOT_APPLICABLE = "not_applicable"
NEEDS_CONFIRMATION = "needs_confirmation"

_EFFECTIVE_LABELS = {
    APPLICABLE: "적용",
    NOT_APPLICABLE: "비적용",
    NEEDS_CONFIRMATION: "확인필요",
    "confirmed_applicable": "적용확인",
    "confirmed_not_applicable": "비적용확인",
    "unresolved": "확인 계속 필요",
    "recheck_required": "재확인 필요",
}

_ELECTRIC_COMPRESSION_SUBTYPES = {
    "turbo",
    "screw",
    "reciprocating",
    "other_compression",
}
_ABSORPTION_SUBTYPES = {"absorption", "direct_fired_absorption"}

_COMMON_ITEMS = {
    1: "냉동기 형식과 무관한 유지관리 점검표 확인 항목입니다.",
    3: "냉동기 형식과 무관한 본체·배관·방진부의 노후 및 부식 확인 항목입니다.",
    14: "냉동기 형식과 무관한 연도별 에너지 사용량 확인 항목입니다.",
}

_ABSORPTION_ITEMS = {
    2: "진공상태와 흡수기 압력을 확인하는 흡수식 계열 항목입니다.",
    9: "가용전은 기존 기준 원문에서 흡수식 냉동기 안전장치로 명시되어 있습니다.",
    11: "수위조절·전극봉·사이트글라스·용액 상태를 확인하는 흡수식 계열 항목입니다.",
}

_COMBUSTION_ITEMS = {
    6: "가스배관·가스버너·배기가스 등 연소장치가 있는 설비에 적용되는 항목입니다.",
    12: "배기가스 온도는 연소장치가 있는 설비에 적용되는 항목입니다.",
}

_CONFIGURATION_REASONS = {
    4: "압축기·재생기와 증발기·응축기의 세부 기준이 형식별로 달라 설비 형식과 제조사 기준 확인이 필요합니다.",
    5: "항목명은 용액·냉매·진공펌프이나 기준 원문은 오일펌프를 다루므로 실제 펌프 구성 확인이 필요합니다.",
    7: "일반 경보와 흡수액 유출 등 흡수식 특유 경보가 함께 있어 실제 경보 구성 확인이 필요합니다.",
    8: "냉수 동결방지 운전 기능의 실제 구성 및 설정 가능 여부 확인이 필요합니다.",
    10: "안전밸브·파열판 등 해당 안전장치의 실제 적용 여부와 검사 대상 여부 확인이 필요합니다.",
    13: "팽창배관·차압밸브·압력계 등 실제 헤더 구성 확인이 필요합니다.",
}

_CONFIRMATION_GUIDANCE = {
    4: (
        "냉동기 세부형식을 확인합니다.",
        "압축식인지 흡수식인지 확인합니다.",
        "해당 형식의 제조사 운전허용압력 또는 운전온도 기준을 확인합니다.",
    ),
    5: (
        "실제 적용된 펌프 종류를 확인합니다.",
        "용액펌프·냉매펌프·진공펌프·오일펌프 중 해당 장치를 확인합니다.",
        "기존 점검기준과 실제 펌프 종류가 일치하는지 확인합니다.",
    ),
    6: (
        "가스버너 또는 기타 연소장치 설치 여부를 확인합니다.",
        "연료 공급 여부를 확인합니다.",
    ),
    7: (
        "일반 냉동기 경보인지 흡수식 특유 경보인지 확인합니다.",
        "최근 경보 및 미조치 사항을 확인합니다.",
    ),
    8: (
        "냉수 동결방지 운전 기능 존재 여부를 확인합니다.",
        "제조사 설정 또는 제어반 기능을 확인합니다.",
    ),
    10: (
        "안전밸브 또는 파열판이 실제 적용되는지 확인합니다.",
        "검사 대상 장치인지 확인합니다.",
    ),
    13: (
        "냉수 또는 냉온수 헤더 구성을 확인합니다.",
        "팽창배관·차압밸브·압력계 적용 여부를 확인합니다.",
    ),
    15: (
        "냉동기 세부형식을 확인합니다.",
        "현재 프로그램의 계산 지원 대상인지 확인합니다.",
        "제조사 또는 설계 COP 기준 존재 여부를 확인합니다.",
    ),
}

_SUBTYPE_FIRST_ITEMS = {2, 6, 9, 11, 12, 15}


def _item_number(item):
    if isinstance(item, dict):
        value = item.get("no")
    else:
        value = item
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def evaluate_chiller_item_applicability(item, subtype_code):
    """Return applicability status and reason for one chiller item.

    ``item`` may be an INSPECTION_DB item dictionary or its stable item
    number. Unknown/malformed item numbers are kept conservative.
    """
    item_no = _item_number(item)
    subtype = normalize_chiller_subtype(subtype_code)

    if item_no in _COMMON_ITEMS:
        return {"status": APPLICABLE, "reason": _COMMON_ITEMS[item_no]}

    if item_no in _ABSORPTION_ITEMS:
        if subtype in _ABSORPTION_SUBTYPES:
            return {"status": APPLICABLE, "reason": _ABSORPTION_ITEMS[item_no]}
        if subtype in _ELECTRIC_COMPRESSION_SUBTYPES:
            return {
                "status": NOT_APPLICABLE,
                "reason": "선택한 압축식 냉동기에는 적용하지 않는 흡수식 계열 항목입니다.",
            }
        return {
            "status": NEEDS_CONFIRMATION,
            "reason": "냉동기 세부유형이 미지정되어 흡수식 계열 적용 여부를 확인해야 합니다.",
        }

    if item_no in _COMBUSTION_ITEMS:
        if subtype == "direct_fired_absorption":
            return {"status": APPLICABLE, "reason": _COMBUSTION_ITEMS[item_no]}
        if subtype in _ELECTRIC_COMPRESSION_SUBTYPES:
            return {
                "status": NOT_APPLICABLE,
                "reason": "선택한 전기 압축식 냉동기는 연소장치를 사용하지 않습니다.",
            }
        if subtype == "absorption":
            return {
                "status": NEEDS_CONFIRMATION,
                "reason": "현재 내부 데이터만으로 흡수식 냉동기의 열원과 연소장치 유무를 단정할 수 없습니다.",
            }
        return {
            "status": NEEDS_CONFIRMATION,
            "reason": "냉동기 세부유형과 연소장치 유무를 확인해야 합니다.",
        }

    if item_no in _CONFIGURATION_REASONS:
        reason = _CONFIGURATION_REASONS[item_no]
        if item_no == 7 and subtype in _ABSORPTION_SUBTYPES:
            reason += " 흡수식 계열과의 관련성은 높지만 항목 전체의 적용 조건은 확정할 수 없습니다."
        return {"status": NEEDS_CONFIRMATION, "reason": reason}

    if item_no == 15:
        if subtype == "turbo":
            return {
                "status": APPLICABLE,
                "reason": "현재 프로젝트 내부 성능계산에서 터보냉동기 COP를 명시적으로 지원합니다.",
            }
        if subtype in _ELECTRIC_COMPRESSION_SUBTYPES:
            return {
                "status": NEEDS_CONFIRMATION,
                "reason": "압축식 냉동기이지만 현재 프로젝트 내부 성능계산은 터보냉동기만 명시적으로 지원합니다.",
            }
        if subtype in _ABSORPTION_SUBTYPES:
            return {
                "status": NEEDS_CONFIRMATION,
                "reason": "기준 원문이 비어 있고 흡수식 계열 COP의 기준·계산 방식이 내부 데이터에 명시되어 있지 않습니다.",
            }
        return {
            "status": NEEDS_CONFIRMATION,
            "reason": "세부유형이 미지정되어 COP 적용 기준과 계산 지원 여부를 확인해야 합니다.",
        }

    return {
        "status": NEEDS_CONFIRMATION,
        "reason": "등록된 냉동기 점검항목 번호가 아니므로 적용성을 확인해야 합니다.",
    }


def chiller_confirmation_guidance(item, subtype_code):
    """Return existing-data-based checks for a needs-confirmation item."""
    item_no = _item_number(item)
    subtype = normalize_chiller_subtype(subtype_code)
    guidance = []

    if subtype == "unspecified" and item_no in _SUBTYPE_FIRST_ITEMS:
        guidance.append("냉동기 세부유형을 먼저 확인합니다.")

    if item_no in (6, 12) and subtype == "absorption":
        guidance.extend(
            (
                "실제 연소식인지 확인합니다.",
                "배기가스가 발생하는 열원인지 확인합니다.",
            )
        )

    guidance.extend(_CONFIRMATION_GUIDANCE.get(item_no, ()))

    if not guidance:
        result = evaluate_chiller_item_applicability(item, subtype)
        if result["status"] == NEEDS_CONFIRMATION:
            guidance.append(result["reason"])

    return guidance


def resolve_effective_applicability(
    base_status, review_data=None, current_subtype="unspecified"
):
    """Resolve a display-only working status without changing stored data."""
    base = (
        base_status
        if base_status in {APPLICABLE, NOT_APPLICABLE, NEEDS_CONFIRMATION}
        else NEEDS_CONFIRMATION
    )
    base_result = {
        "status": base,
        "label": _EFFECTIVE_LABELS[base],
        "needs_recheck": False,
        "reason": "사용자 확인결과가 없어 기본 적용성을 표시합니다.",
    }
    if not isinstance(review_data, dict):
        return base_result

    review_status = review_data.get("상태", "")
    if review_status not in {
        "confirmed_applicable",
        "confirmed_not_applicable",
        "unresolved",
    }:
        return base_result

    current = normalize_chiller_subtype(current_subtype)
    reviewed = normalize_chiller_subtype(
        review_data.get("확인당시세부유형", "unspecified")
    )
    if reviewed != current:
        return {
            "status": "recheck_required",
            "label": _EFFECTIVE_LABELS["recheck_required"],
            "needs_recheck": True,
            "reason": "사용자 확인 당시 냉동기 세부유형과 현재 세부유형이 다릅니다.",
        }

    conflict = (
        base == APPLICABLE
        and review_status == "confirmed_not_applicable"
    ) or (
        base == NOT_APPLICABLE
        and review_status == "confirmed_applicable"
    )
    if conflict:
        return {
            "status": "recheck_required",
            "label": _EFFECTIVE_LABELS["recheck_required"],
            "needs_recheck": True,
            "reason": "현재 기본 적용성과 과거 사용자 확인결과가 서로 충돌합니다.",
        }

    if base == NEEDS_CONFIRMATION:
        return {
            "status": review_status,
            "label": _EFFECTIVE_LABELS[review_status],
            "needs_recheck": False,
            "reason": "현재 세부유형과 일치하는 사용자 확인결과를 표시합니다.",
        }

    if (
        base == APPLICABLE
        and review_status == "confirmed_applicable"
    ) or (
        base == NOT_APPLICABLE
        and review_status == "confirmed_not_applicable"
    ):
        return {
            "status": review_status,
            "label": _EFFECTIVE_LABELS[review_status],
            "needs_recheck": False,
            "reason": "기본 적용성과 사용자 확인결과가 일치합니다.",
        }

    return {
        "status": base,
        "label": _EFFECTIVE_LABELS[base],
        "needs_recheck": False,
        "reason": "현재 기본 적용성이 명확하여 기본 상태를 표시합니다.",
    }
