from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from .judgment import (
    calculate_deviation,
    is_final_fail as is_final_fail_value,
    is_final_na as is_final_na_value,
    is_final_pass as is_final_pass_value,
    is_measurement_item_data,
    is_outside_tolerance,
    normalize_final_judgment as normalize_judgment_value,
    parse_numeric_value,
)


MEASUREMENT_APPLICABILITY_DEFAULTS = {
    "mode": "all",
    "equipment_subtype": [],
    "requires_combustion": None,
    "note": "",
}

MEASUREMENT_CRITERION_DEFAULTS = {
    "name": "",
    "measure_type": "",
    "unit": "",
    "comparison": "manual",
    "lower": None,
    "upper": None,
    "tolerance_pct": None,
    "ratio_min": None,
    "ratio_max": None,
    "reference_source": "manual",
    "auto_review": "manual",
    "applicability": {
        "mode": "all",
        "equipment_subtype": [],
        "requires_combustion": None,
        "note": "",
    },
    "operands": {
        "left": "",
        "right": "",
    },
    "difference_mode": "manual",
}

MEASUREMENT_DIFFERENCE_MODE_OPTIONS = {
    "directional",
    "absolute",
    "manual",
}

INSPECTION_METHOD_OPTIONS = (
    "visual",
    "operation_test",
    "measurement",
    "document",
    "existing_data",
    "bms",
)

INSPECTION_STATUS_OPTIONS = (
    "checked",
    "unavailable",
    "not_applicable",
    "not_checked",
    "unused",
)

CRITERION_JUDGMENT_OPTIONS = (
    "unset",
    "pass",
    "fail",
)

UNAVAILABLE_REASON_OPTIONS = (
    "equipment_stopped",
    "access_impossible",
    "measurement_point_missing",
    "measurement_impossible",
    "operating_condition_not_met",
    "document_unavailable",
    "safety_restriction",
    "other",
)

CRITERION_SUBSTITUTION_DEFAULTS = {
    "used": False,
    "method": "",
    "basis": "",
    "source_document": "",
    "note": "",
}

CRITERION_RESULT_DEFAULTS = {
    "criterion_index": None,
    "criterion_name": "",
    "performed_methods": [],
    "inspection_status": "not_checked",
    "criterion_judgment": "unset",
    "unavailable_reason": "",
    "substitution": CRITERION_SUBSTITUTION_DEFAULTS,
    "evidence_note": "",
}

MEASUREMENT_METADATA_DEFAULTS = {
    "measure_type": "",
    "unit": "",
    "comparison": "manual",
    "lower": None,
    "upper": None,
    "tolerance_pct": None,
    "review_type": "",
    "measurement_device": "",
    "ratio_min": None,
    "ratio_max": None,
    "applicability": MEASUREMENT_APPLICABILITY_DEFAULTS,
    "reference_source": "manual",
    "auto_review": "manual",
    "criteria": [],
}


def _new_measurement_metadata():
    metadata = dict(MEASUREMENT_METADATA_DEFAULTS)
    metadata["applicability"] = dict(
        MEASUREMENT_APPLICABILITY_DEFAULTS
    )
    metadata["applicability"]["equipment_subtype"] = []
    metadata["criteria"] = []
    return metadata


def _new_measurement_criterion():
    criterion = dict(MEASUREMENT_CRITERION_DEFAULTS)
    criterion["applicability"] = {
        "mode": "all",
        "equipment_subtype": [],
        "requires_combustion": None,
        "note": "",
    }
    criterion["operands"] = {"left": "", "right": ""}
    criterion["difference_mode"] = "manual"
    return criterion


def measurement_metadata_for(item_data):
    """Normalize missing, v1, or v2 metadata to the complete v2 schema."""
    metadata = _new_measurement_metadata()
    if isinstance(item_data, dict):
        candidate = item_data.get("measurement_metadata", {})
        if isinstance(candidate, dict):
            metadata.update(
                {
                    key: candidate[key]
                    for key in metadata
                    if key in candidate
                    and key not in {"applicability", "criteria"}
                }
            )

            applicability = candidate.get("applicability", {})
            if isinstance(applicability, dict):
                metadata["applicability"].update(
                    {
                        key: applicability[key]
                        for key in metadata["applicability"]
                        if key in applicability
                    }
                )
                subtypes = metadata["applicability"].get(
                    "equipment_subtype", []
                )
                metadata["applicability"]["equipment_subtype"] = (
                    list(subtypes)
                    if isinstance(subtypes, (list, tuple))
                    else []
                )

            criteria = candidate.get("criteria", [])
            if isinstance(criteria, list):
                for criterion in criteria:
                    if not isinstance(criterion, dict):
                        continue
                    normalized = _new_measurement_criterion()
                    normalized.update(
                        {
                            key: criterion[key]
                            for key in normalized
                            if key in criterion
                            and key not in {
                                "applicability",
                                "operands",
                                "difference_mode",
                            }
                        }
                    )

                    applicability = criterion.get(
                        "applicability", {}
                    )
                    if isinstance(applicability, dict):
                        mode = applicability.get("mode")
                        if (
                            isinstance(mode, str)
                            and mode in {"all", "conditional"}
                        ):
                            normalized["applicability"]["mode"] = mode
                        subtypes = applicability.get(
                            "equipment_subtype"
                        )
                        if isinstance(subtypes, (list, tuple)):
                            normalized["applicability"][
                                "equipment_subtype"
                            ] = [
                                subtype
                                for subtype in subtypes
                                if isinstance(subtype, str)
                            ]
                        combustion = applicability.get(
                            "requires_combustion"
                        )
                        if (
                            combustion is None
                            or isinstance(combustion, bool)
                        ):
                            normalized["applicability"][
                                "requires_combustion"
                            ] = combustion
                        note = applicability.get("note")
                        if isinstance(note, str):
                            normalized["applicability"]["note"] = note

                    operands = criterion.get("operands", {})
                    if isinstance(operands, dict):
                        for operand_name in ("left", "right"):
                            operand = operands.get(operand_name)
                            if isinstance(operand, str):
                                normalized["operands"][
                                    operand_name
                                ] = operand

                    difference_mode = criterion.get(
                        "difference_mode"
                    )
                    if (
                        isinstance(difference_mode, str)
                        and difference_mode
                        in MEASUREMENT_DIFFERENCE_MODE_OPTIONS
                    ):
                        normalized["difference_mode"] = difference_mode
                    metadata["criteria"].append(normalized)
    return metadata


def _new_criterion_result():
    result = dict(CRITERION_RESULT_DEFAULTS)
    result["performed_methods"] = []
    result["substitution"] = dict(
        CRITERION_SUBSTITUTION_DEFAULTS
    )
    return result


def _legacy_criterion_status(judgment):
    normalized = normalize_judgment_value(judgment)
    if normalized == "/ 해당없음":
        return "not_applicable"
    if normalized == "미사용":
        return "unused"
    return "not_checked"


def normalize_criterion_result(
    value,
    criterion_index=None,
    criterion_name="",
    default_status="not_checked",
):
    """Return a new, canonical criterion execution-result dictionary."""
    candidate = value if isinstance(value, dict) else {}
    normalized = _new_criterion_result()

    index = criterion_index
    if not isinstance(index, int) or isinstance(index, bool) or index < 0:
        index = candidate.get("criterion_index")
    if isinstance(index, int) and not isinstance(index, bool) and index >= 0:
        normalized["criterion_index"] = index

    name = criterion_name
    if not isinstance(name, str) or not name:
        name = candidate.get("criterion_name", "")
    if isinstance(name, str):
        normalized["criterion_name"] = name

    methods = candidate.get("performed_methods", [])
    if isinstance(methods, (list, tuple)):
        seen = set()
        for method in methods:
            if (
                method in INSPECTION_METHOD_OPTIONS
                and method not in seen
            ):
                normalized["performed_methods"].append(method)
                seen.add(method)

    status = candidate.get("inspection_status", default_status)
    normalized["inspection_status"] = (
        status
        if status in INSPECTION_STATUS_OPTIONS
        else "not_checked"
    )

    judgment = candidate.get("criterion_judgment", "unset")
    if (
        normalized["inspection_status"] == "checked"
        and judgment in {"pass", "fail"}
    ):
        normalized["criterion_judgment"] = judgment

    reason = candidate.get("unavailable_reason", "")
    if (
        normalized["inspection_status"] == "unavailable"
        and reason in UNAVAILABLE_REASON_OPTIONS
    ):
        normalized["unavailable_reason"] = reason

    substitution = candidate.get("substitution", {})
    if isinstance(substitution, dict) and substitution.get("used") is True:
        normalized["substitution"]["used"] = True
        method = substitution.get("method", "")
        if method in INSPECTION_METHOD_OPTIONS:
            normalized["substitution"]["method"] = method
        for field in ("basis", "source_document", "note"):
            text = substitution.get(field, "")
            if isinstance(text, str):
                normalized["substitution"][field] = text

    evidence_note = candidate.get("evidence_note", "")
    if isinstance(evidence_note, str):
        normalized["evidence_note"] = evidence_note

    return normalized


def normalize_criteria_results(
    criteria,
    values=None,
    legacy_judgment="",
):
    """Normalize optional row-level criteria_results without mutating inputs."""
    criteria = criteria if isinstance(criteria, list) else []
    values = values if isinstance(values, list) else []
    default_status = _legacy_criterion_status(legacy_judgment)

    if not criteria:
        return [
            normalize_criterion_result(
                value,
                default_status=default_status,
            )
            for value in values
        ]

    indexed = {}
    named = {}
    for position, value in enumerate(values):
        if not isinstance(value, dict):
            continue
        index = value.get("criterion_index")
        if (
            isinstance(index, int)
            and not isinstance(index, bool)
            and index >= 0
            and index not in indexed
        ):
            indexed[index] = (position, value)
        name = value.get("criterion_name")
        if isinstance(name, str) and name:
            named.setdefault(name, []).append((position, value))

    used_positions = set()
    results = []
    for index, criterion in enumerate(criteria):
        name = (
            criterion.get("name", "")
            if isinstance(criterion, dict)
            else str(criterion or "")
        )
        selected = indexed.get(index)
        if selected and selected[0] in used_positions:
            selected = None
        if selected is None:
            for named_result in named.get(name, []):
                if named_result[0] not in used_positions:
                    selected = named_result
                    break
        if selected is None:
            value = {}
        else:
            used_positions.add(selected[0])
            value = selected[1]
        results.append(
            normalize_criterion_result(
                value,
                criterion_index=index,
                criterion_name=name,
                default_status=default_status,
            )
        )
    return results


def evaluate_criteria_completion(criteria, values=None):
    """Return a derived completion summary without mutating stored data."""
    criteria = criteria if isinstance(criteria, list) else []
    results = normalize_criteria_results(criteria, values)
    summary = {
        "state": "no_criteria",
        "total": len(criteria),
        "applicable": 0,
        "checked": 0,
        "pass": 0,
        "fail": 0,
        "unavailable": 0,
        "not_checked": 0,
        "not_applicable": 0,
        "unused": 0,
        "unset_judgment": 0,
    }
    if not criteria:
        return summary

    for result in results:
        status = result["inspection_status"]
        judgment = result["criterion_judgment"]
        summary[status] += 1
        if status != "not_applicable":
            summary["applicable"] += 1
        if status == "checked":
            if judgment in {"pass", "fail"}:
                summary[judgment] += 1
            else:
                summary["unset_judgment"] += 1

    if summary["not_applicable"] == summary["total"]:
        summary["state"] = "all_not_applicable"
    elif (
        summary["unavailable"]
        or summary["unused"]
        or summary["fail"]
    ):
        summary["state"] = "review_required"
    elif summary["not_checked"] or summary["unset_judgment"]:
        summary["state"] = "incomplete"
    else:
        summary["state"] = "complete"
    return summary


def derive_final_judgment_from_criteria(criteria, values=None):
    """Derive the row judgment once criterion execution has been recorded.

    ``None`` means the mixed state requires a user's decision.  In particular,
    unavailable is represented conservatively as 미점검 and is never treated
    as an automatic failure.
    """
    summary = evaluate_criteria_completion(criteria, values)
    if summary["state"] == "no_criteria":
        return None
    if summary["fail"]:
        return "X 불합격"
    if summary["unavailable"] or summary["not_checked"] or summary["unset_judgment"]:
        return "미점검"
    if summary["not_applicable"] == summary["total"]:
        return "/ 해당없음"
    if summary["unused"] == summary["total"]:
        return "미사용"
    if summary["unused"]:
        return None
    applicable_checked = summary["checked"]
    if (
        applicable_checked > 0
        and summary["pass"] == applicable_checked
        and applicable_checked + summary["not_applicable"] == summary["total"]
    ):
        return "○ 합격"
    return "미점검"


def criteria_judgment_warnings(
    criteria,
    values=None,
    final_judgment="",
):
    """Return criterion/final-judgment conflicts without changing either."""
    summary = evaluate_criteria_completion(criteria, values)
    if summary["state"] == "no_criteria":
        return []

    final = normalize_judgment_value(final_judgment)
    warnings = []
    if final == "○ 합격":
        if summary["fail"]:
            warnings.append(
                "부적합 criterion이 있으나 최종판정이 합격입니다."
            )
        if summary["unavailable"]:
            warnings.append(
                "확인불가 criterion이 있으나 최종판정이 합격입니다."
            )
        if summary["not_checked"]:
            warnings.append(
                "미점검 criterion이 있으나 최종판정이 합격입니다."
            )
        if summary["unset_judgment"]:
            warnings.append(
                "미판정 criterion이 있으나 최종판정이 합격입니다."
            )

    if (
        final == "X 불합격"
        and summary["applicable"] > 0
        and summary["pass"] == summary["applicable"]
    ):
        warnings.append(
            "모든 criterion은 적합이나 최종판정은 불합격입니다."
        )

    if (
        summary["state"] == "all_not_applicable"
        and final != "/ 해당없음"
    ):
        warnings.append(
            "모든 criterion이 해당없음이나 최종판정이 해당없음이 아닙니다."
        )

    if final == "/ 해당없음" and summary["checked"]:
        warnings.append(
            "확인완료 criterion이 있으나 최종판정이 해당없음입니다."
        )

    if summary["unused"] and final in {"○ 합격", "X 불합격"}:
        warnings.append(
            "미사용 criterion이 있으나 최종판정이 합격 또는 불합격입니다."
        )
    return warnings


def criterion_preflight_issues(
    criteria,
    values=None,
    final_judgment="",
    results_present=True,
):
    """Return report-preflight issues without changing stored judgments."""
    criteria = criteria if isinstance(criteria, list) else []
    if not criteria:
        return []

    if not results_present or not isinstance(values, list) or not values:
        return [
            {
                "severity": "warning",
                "code": "criteria_results_missing",
                "criterion_index": None,
                "criterion_name": "",
                "message": "criterion 수행기록이 없습니다.",
            }
        ]

    results = normalize_criteria_results(criteria, values)
    summary = evaluate_criteria_completion(criteria, values)
    final = normalize_judgment_value(final_judgment)
    issues = []

    def add(severity, code, message, index=None, name=""):
        issues.append(
            {
                "severity": severity,
                "code": code,
                "criterion_index": index,
                "criterion_name": name,
                "message": message,
            }
        )

    for index, result in enumerate(results):
        name = result.get("criterion_name", "") or f"criterion {index + 1}"
        status = result["inspection_status"]
        judgment = result["criterion_judgment"]

        if status == "not_checked":
            add(
                "error" if final == "○ 합격" else "warning",
                "not_checked_with_pass" if final == "○ 합격" else "not_checked",
                "미점검 criterion이 있습니다.",
                index,
                name,
            )
        elif status == "unavailable":
            add(
                "error" if final == "○ 합격" else "warning",
                "unavailable_with_pass" if final == "○ 합격" else "unavailable",
                "확인불가 criterion이 있습니다.",
                index,
                name,
            )
        elif status == "checked":
            if judgment == "unset":
                add(
                    "warning",
                    "checked_without_judgment",
                    "확인완료 criterion의 판정이 입력되지 않았습니다.",
                    index,
                    name,
                )
            if not result.get("performed_methods"):
                add(
                    "warning",
                    "checked_without_method",
                    "확인완료 criterion의 수행방법이 기록되지 않았습니다.",
                    index,
                    name,
                )

        if status == "checked" and judgment == "fail" and final == "○ 합격":
            add(
                "error",
                "criterion_fail_with_pass",
                "부적합 criterion이 있으나 최종판정이 합격입니다.",
                index,
                name,
            )

        substitution = result.get("substitution", {})
        if isinstance(substitution, dict) and substitution.get("used") is True:
            if not any(
                str(substitution.get(field, "") or "").strip()
                for field in ("method", "basis", "source_document")
            ):
                add(
                    "warning",
                    "substitution_details_missing",
                    "대체 확인을 사용했으나 방법·근거·출처문서가 기록되지 않았습니다.",
                    index,
                    name,
                )

    if summary["state"] == "all_not_applicable" and final != "/ 해당없음":
        add(
            "warning",
            "all_not_applicable_mismatch",
            "모든 criterion이 해당없음이나 최종판정이 해당없음이 아닙니다.",
        )
    if final == "/ 해당없음" and summary["checked"]:
        add(
            "warning",
            "checked_with_not_applicable_final",
            "확인완료 criterion이 있으나 최종판정이 해당없음입니다.",
        )
    if summary["unused"] and final in {"○ 합격", "X 불합격"}:
        add(
            "warning",
            "unused_with_final_judgment",
            "미사용 criterion이 있으나 최종판정이 합격 또는 불합격입니다.",
        )
    return issues


class InspectionServiceMixin:
    @staticmethod
    def measurement_metadata(item_data):
        return measurement_metadata_for(item_data)

    @staticmethod
    def criterion_preflight_issues(
        criteria,
        values=None,
        final_judgment="",
        results_present=True,
    ):
        return criterion_preflight_issues(
            criteria,
            values,
            final_judgment,
            results_present,
        )

    @staticmethod
    def is_measurement_item(item_data):
        return is_measurement_item_data(item_data)

    @staticmethod
    def normalize_final_judgment(value):
        return normalize_judgment_value(value)

    @staticmethod
    def is_final_pass(value):
        return is_final_pass_value(value)

    @staticmethod
    def is_final_fail(value):
        return is_final_fail_value(value)

    @staticmethod
    def is_final_na(value):
        return is_final_na_value(value)

    def default_pass_reason(self, row):
        item_name = self.table_item_text(
            self.inspection_detail_table, row, 1
        )
        method = self.table_item_text(
            self.inspection_detail_table, row, 2
        )
        input_type = self.table_item_text(
            self.inspection_detail_table, row, 4
        )
        design = self.table_item_text(
            self.inspection_detail_table, row, 5
        )
        measured = self.table_item_text(
            self.inspection_detail_table, row, 6
        )
        unit = self.table_item_text(
            self.inspection_detail_table, row, 7
        )
        tolerance = self.table_item_text(
            self.inspection_detail_table, row, 8
        )
        deviation = self.table_item_text(
            self.inspection_detail_table, row, 9
        )

        # 에너지 사용량은 8번 에너지 분석값을 직접 연동
        if item_name == "에너지 사용량":
            energy_comment = self.current_energy_linked_comment()
            if energy_comment:
                return "[에너지자동] " + energy_comment

        if input_type == "측정":
            # 수치가 실제로 입력된 경우만 수치형 합격문구 생성
            def numeric(text):
                try:
                    return float(
                        str(text)
                        .replace(",", "")
                        .strip()
                    )
                except (TypeError, ValueError):
                    return None

            d_val = numeric(design)
            m_val = numeric(measured)

            display_unit = unit.strip()

            # 설계/측정값 모두 있으면 비율까지 자동 기술
            if (
                d_val is not None
                and m_val is not None
                and d_val != 0
            ):
                ratio = m_val / d_val * 100.0
                parts = [
                    f"설계·정격값 {design}{display_unit}",
                    f"측정값 {measured}{display_unit}",
                    f"설계값 대비 {ratio:.1f}%",
                ]

                if deviation and deviation != "-":
                    parts.append(
                        f"편차 {deviation}%"
                    )
                if tolerance:
                    parts.append(
                        f"허용편차 ±{tolerance}% 이내"
                    )

                # 항목 특성별 자연스러운 마무리
                if "유량" in item_name:
                    parts.append(
                        "유량 성능이 점검기준 범위 내로 확인됨"
                    )
                elif "전류" in item_name:
                    parts.append(
                        "운전전류가 정격 및 점검기준 범위 내로 확인됨"
                    )
                elif "압력" in item_name:
                    parts.append(
                        "운전압력이 설계·제조사 기준 범위 내로 확인됨"
                    )
                elif "소음" in item_name or "진동" in item_name:
                    parts.append(
                        "측정결과 관리기준 범위 내로 확인됨"
                    )
                elif "온도" in item_name:
                    parts.append(
                        "온도 측정값이 점검기준 범위 내로 확인됨"
                    )
                else:
                    parts.append(
                        "설계·정격값 및 점검기준과 비교하여 허용범위 내로 확인됨"
                    )

                return ", ".join(parts)

            # 측정값만 존재하는 경우
            if measured:
                parts = [
                    f"측정값 {measured}{display_unit}"
                ]
                if deviation and deviation != "-":
                    parts.append(
                        f"편차 {deviation}%"
                    )
                parts.append(
                    "점검기준과 비교하여 적정 범위로 확인됨"
                )
                return ", ".join(parts)

            # 측정항목인데 실제 수치가 없으면 합격문구를 만들어주지 않는다.
            return (
                "[측정값 입력 필요] 합격 판정 근거가 되는 실제 측정값을 입력한 후 "
                "기술적 소견을 확정하십시오."
            )

        if "작동" in item_name or "운전" in item_name:
            return "현장 작동시험 결과 정상적으로 운전되며 이상상태가 확인되지 않음."
        if "누수" in item_name:
            return "육안점검 결과 누수 및 누수흔적이 확인되지 않음."
        if "소음" in item_name or "진동" in item_name:
            return "운전 중 이상소음 및 비정상 진동이 확인되지 않음."
        if "부식" in item_name:
            return "육안점검 결과 기능에 영향을 주는 유해한 부식이 확인되지 않음."
        if "안전" in item_name or "경보" in item_name or "인터록" in item_name:
            return "작동시험 및 상태확인 결과 안전·경보·인터록 기능이 정상임."
        if "필터" in item_name:
            return "필터 상태 및 압력손실을 확인한 결과 운전에 지장을 주는 이상이 확인되지 않음."

        return (
            f"{method or '현장점검'} 결과 점검기준에 부합하며 "
            "기능상 이상이 확인되지 않음."
        )

    @staticmethod
    def default_fail_reason():
        return (
            "[불합격 사유 입력 필요] "
            "측정값·기준·이상상태·영향을 구체적으로 작성하십시오."
        )

    def technical_opinion_candidates(self, row, judgment=None):
        """Return existing opinion sources without changing the saved value."""
        if row < 0 or row >= self.inspection_detail_table.rowCount():
            return []
        normalized = self.normalize_final_judgment(
            judgment or self.current_detail_final_judgment(row)
        )
        current_item = self.inspection_detail_table.item(row, 11)
        current = current_item.text().strip() if current_item else ""
        pass_reason = self.default_pass_reason(row)
        fail_reason = self.default_fail_reason()

        candidates = []
        seen = set()

        def add(label, text, source):
            value = str(text or "").strip()
            if not value or value in seen:
                return
            seen.add(value)
            candidates.append(
                {"label": label, "text": value, "source": source}
            )

        if normalized == "X 불합격":
            add("기본 이상 소견", fail_reason, "default_fail")
            add("기본 정상 소견", pass_reason, "default_pass")
        else:
            add("기본 정상 소견", pass_reason, "default_pass")
            add("기본 이상 소견", fail_reason, "default_fail")
        add("현재 작성 소견", current, "current")

        current_key = getattr(self, "current_detail_equipment_key", None)
        current_target = (
            self.find_target_data_by_key(current_key)
            if current_key and hasattr(self, "find_target_data_by_key")
            else None
        )
        current_equipment_id = str(
            (current_target or {}).get("equipment_id", "") or ""
        ).strip()
        current_type = str(
            (current_target or {}).get("설비종류", "") or ""
        ).strip()
        item_name = self.table_item_text(self.inspection_detail_table, row, 1)

        for target_key, result_rows in reversed(
            list(getattr(self, "inspection_results", {}).items())
        ):
            if not isinstance(result_rows, list) or row >= len(result_rows):
                continue
            target = (
                self.find_target_data_by_key(target_key)
                if hasattr(self, "find_target_data_by_key")
                else None
            )
            target_equipment_id = str(
                (target or {}).get("equipment_id", "") or ""
            ).strip()
            target_type = str(
                (target or {}).get("설비종류", "") or ""
            ).strip()
            if current_equipment_id:
                if target_equipment_id != current_equipment_id:
                    continue
            elif target_key != current_key:
                continue
            if current_type and target_type and target_type != current_type:
                continue
            saved_row = result_rows[row]
            if not isinstance(saved_row, dict):
                continue
            saved_name = str(saved_row.get("점검항목", "") or "").strip()
            if saved_name and item_name and saved_name != item_name:
                continue
            add(
                "기존 작성 소견",
                saved_row.get("기술적소견", ""),
                "history",
            )
        return candidates


    def on_final_judgment_changed(self, row, judgment):
        normalized = self.normalize_final_judgment(judgment)
        combo = self.inspection_detail_table.cellWidget(row, 10)

        if (
            row in getattr(self, "_criteria_results_should_save", set())
            and hasattr(self, "criteria_for_detail_row")
        ):
            criteria = self.criteria_for_detail_row(row)
            derived = derive_final_judgment_from_criteria(
                criteria,
                getattr(self, "_criteria_results_by_row", {}).get(row, []),
            )
            if derived and normalized != derived:
                normalized = derived
                if hasattr(self, "status_label"):
                    self.status_label.setText(
                        "이 항목은 저장된 점검기준 수행결과를 기준으로 "
                        f"최종판정이 {derived}(으)로 유지됩니다."
                    )

        if combo and combo.currentText() != normalized:
            combo.blockSignals(True)
            combo.setCurrentText(normalized)
            combo.blockSignals(False)

        opinion_item = self.inspection_detail_table.item(row, 11)
        if opinion_item is None:
            opinion_item = QTableWidgetItem("")
            self.inspection_detail_table.setItem(row, 11, opinion_item)

        # 판정 변경은 소견 후보의 우선순위와 배경만 바꾼다. 기존 사용자
        # 문구를 삭제하거나 정상/이상 소견으로 자동 교체하지 않는다.
        if normalized == "○ 합격":
            opinion_item.setBackground(QColor("white"))

        elif normalized == "X 불합격":
            opinion_item.setBackground(QColor("#ffe2e2"))

        elif normalized in {"/ 해당없음", "미사용"}:
            opinion_item.setBackground(QColor("white"))

        else:
            opinion_item.setBackground(QColor("white"))

        if hasattr(self, "refresh_technical_opinion_candidates"):
            self.refresh_technical_opinion_candidates(row)

        # RCA active targets follow the current row-level final judgment.
        # Criterion judgments remain independent and never create RCA targets.
        if (
            getattr(self, "current_detail_equipment_key", None)
            and hasattr(self, "refresh_cause_analysis_table")
        ):
            self.save_current_inspection_detail()
            self.refresh_cause_analysis_table()

    def refresh_auto_pass_reason_for_row(self, row):
        combo = self.inspection_detail_table.cellWidget(
            row, 10
        )
        if not combo or not self.is_final_pass(
            combo.currentText()
        ):
            return

        opinion_item = self.inspection_detail_table.item(
            row, 11
        )
        if opinion_item is None:
            opinion_item = QTableWidgetItem("")
            self.inspection_detail_table.setItem(
                row, 11, opinion_item
            )

        current = opinion_item.text().strip()

        auto_like = (
            not current
            or current.startswith("[측정값 입력 필요]")
            or current.startswith("[에너지자동]")
            or current.startswith("[자동검토]")
            or "설계·정격값 및 점검기준과 비교하여 허용범위 내로 확인됨" in current
            or "측정값 " in current and "점검기준" in current
        )

        if auto_like:
            opinion_item.setText(
                self.default_pass_reason(row)
            )

    def validate_final_judgments(self, show_message=True):
        self.save_current_inspection_detail()

        missing_reason = []
        uninspected = []
        pass_without_measurement = []

        for target_row in range(self.target_table.rowCount()):
            target = self.target_row_data(target_row)
            key = self.target_key_from_row(target_row)

            for item in self.inspection_results.get(key, []):
                judgment = self.normalize_final_judgment(
                    item.get("판정", "")
                )

                if judgment == "미점검":
                    uninspected.append(
                        f"{target.get('설비종류','')} / "
                        f"{target.get('관리번호','') or '관리번호 미지정'} / "
                        f"{item.get('점검내용','')}"
                    )

                if (
                    judgment == "○ 합격"
                    and item.get("입력구분") == "측정"
                    and not str(
                        item.get("측정확인값", "")
                    ).strip()
                ):
                    pass_without_measurement.append(
                        f"{target.get('설비종류','')} / "
                        f"{target.get('관리번호','') or '관리번호 미지정'} / "
                        f"{item.get('점검내용','')}"
                    )

                if judgment == "X 불합격":
                    opinion = str(
                        item.get("기술적소견", "")
                    ).strip()

                    if (
                        not opinion
                        or opinion.startswith("[불합격 사유 입력 필요]")
                    ):
                        missing_reason.append(
                            f"{target.get('설비종류','')} / "
                            f"{target.get('관리번호','') or '관리번호 미지정'} / "
                            f"{item.get('점검내용','')}"
                        )

        if missing_reason and show_message:
            preview = "\n".join(missing_reason[:10])
            if len(missing_reason) > 10:
                preview += f"\n... 외 {len(missing_reason)-10}건"

            QMessageBox.warning(
                self,
                "불합격 사유 입력 필요",
                "X 불합격 항목은 기술적 사유가 반드시 필요합니다.\n\n"
                + preview,
            )
            self.menu.setCurrentRow(3)
            if hasattr(self, "inspection_tabs"):
                self.inspection_tabs.setCurrentIndex(2)

        return {
            "불합격사유누락": missing_reason,
            "미점검": uninspected,
            "측정값없는합격": pass_without_measurement,
            "통과": not missing_reason,
        }

    @staticmethod
    def numeric_value(text):
        return parse_numeric_value(text)

    def on_inspection_measurement_changed(self, item):
        if item.column() not in (5, 6, 8):
            return

        row = item.row()
        input_type = self.table_item_text(
            self.inspection_detail_table, row, 4
        )

        if input_type != "측정":
            return

        design = self.numeric_value(
            self.table_item_text(
                self.inspection_detail_table, row, 5
            )
        )
        measured = self.numeric_value(
            self.table_item_text(
                self.inspection_detail_table, row, 6
            )
        )
        tolerance = self.numeric_value(
            self.table_item_text(
                self.inspection_detail_table, row, 8
            )
        )

        self.inspection_detail_table.blockSignals(True)
        try:
            deviation_item = self.inspection_detail_table.item(row, 9)
            if deviation_item is None:
                deviation_item = QTableWidgetItem("")
                deviation_item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable
                )
                self.inspection_detail_table.setItem(
                    row, 9, deviation_item
                )

            if (
                design is None
                or measured is None
                or design == 0
            ):
                deviation_item.setText("")
                return

            deviation = calculate_deviation(
                measured,
                design,
            )
            deviation_item.setText(
                f"{deviation:+.2f}"
            )

            # 성능계산은 최종 합격/불합격을 자동 확정하지 않는다.
            # 허용편차 초과 여부만 기술검토 알림으로 남긴다.
            if tolerance is not None:
                opinion_item = self.inspection_detail_table.item(
                    row, 11
                )
                if opinion_item is None:
                    opinion_item = QTableWidgetItem("")
                    self.inspection_detail_table.setItem(
                        row, 11, opinion_item
                    )

                current = opinion_item.text().strip()
                if is_outside_tolerance(deviation, tolerance):
                    alert = (
                        f"[자동검토] 설계·정격값 대비 편차 {deviation:+.2f}%로 "
                        f"허용편차 ±{abs(tolerance):.2f}% 초과. "
                        "운전조건·부하율·계측오차를 확인한 후 최종 합격/불합격 판정 필요."
                    )
                    if (
                        not current
                        or current.startswith("[자동검토]")
                    ):
                        opinion_item.setText(alert)
                    opinion_item.setBackground(QColor("#fff2cc"))
                else:
                    if current.startswith("[자동검토]"):
                        opinion_item.setText(
                            self.default_pass_reason(row)
                        )
                    opinion_item.setBackground(QColor("white"))
        finally:
            self.inspection_detail_table.blockSignals(False)
