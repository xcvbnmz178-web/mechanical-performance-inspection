"""Build report read models from project dictionaries without mutation."""

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .model import (
    CalculationEntry,
    CriterionExecution,
    EnergyAnalysisSection,
    EngineerEntry,
    EquipmentEntry,
    ImprovementPlanEntry,
    InspectionItemResult,
    InspectionTargetSection,
    PhotoEntry,
    PreviousComparisonEntry,
    ReportDocument,
    RootCauseEntry,
    SiteSection,
    SystemReviewEntry,
)


REPORT_MODEL_VERSION = "1.0"


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(dict(value)) if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [_mapping(row) for row in value if isinstance(row, Mapping)]


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _target_key(target: Mapping[str, Any], target_row: int) -> str:
    return "|".join(
        (
            _text(target.get("설비종류", "")),
            _text(target.get("점검번호", "")),
            _text(target.get("장비대장행", -1)),
            str(target_row),
        )
    )


def _criterion(value: Mapping[str, Any]) -> CriterionExecution:
    index = value.get("criterion_index")
    if not isinstance(index, int) or isinstance(index, bool):
        index = None
    methods = value.get("performed_methods", [])
    return CriterionExecution(
        criterion_index=index,
        criterion_name=_text(value.get("criterion_name", "")),
        performed_methods=(
            [_text(item) for item in methods]
            if isinstance(methods, list)
            else []
        ),
        inspection_status=_text(value.get("inspection_status", "")),
        criterion_judgment=_text(value.get("criterion_judgment", "")),
        unavailable_reason=_text(value.get("unavailable_reason", "")),
        substitution=_mapping(value.get("substitution", {})),
        evidence_note=_text(value.get("evidence_note", "")),
    )


def _photo(
    value: Mapping[str, Any], equipment_id: str = ""
) -> PhotoEntry:
    raw = _mapping(value)
    item_label = _text(value.get("점검항목", "")).strip()
    number_prefix, separator, _rest = item_label.partition(".")
    item_no = number_prefix.strip() if separator and number_prefix.strip().isdigit() else ""
    return PhotoEntry(
        equipment_id=equipment_id,
        target_key=_text(value.get("장비키", "")),
        item_no=item_no,
        file_path=_text(value.get("저장경로", "")),
        caption=_text(value.get("설명", "")),
        category=_text(value.get("사진구분", "")),
        note=_text(value.get("촬영목록항목", "")),
        raw=raw,
    )


def _inspection_item(
    value: Mapping[str, Any], photos: list[PhotoEntry]
) -> InspectionItemResult:
    raw = _mapping(value)
    criteria_values = value.get("criteria_results", [])
    criteria = (
        [_criterion(item) for item in criteria_values if isinstance(item, Mapping)]
        if isinstance(criteria_values, list)
        else []
    )
    known = {
        "번호", "점검내용", "점검항목", "점검방법", "점검기준",
        "측정확인값", "설계정격값", "정격값", "판정", "기술적소견",
        "criteria_results", "equipment_id",
    }
    return InspectionItemResult(
        item_no=_text(value.get("번호", "")),
        item_name=_text(value.get("점검내용", value.get("점검항목", ""))),
        inspection_method=_text(value.get("점검방법", "")),
        inspection_criteria=_text(value.get("점검기준", "")),
        measured_value=deepcopy(value.get("측정확인값", "")),
        design_value=deepcopy(value.get("설계정격값", "")),
        rated_value=deepcopy(value.get("정격값", "")),
        judgment=_text(value.get("판정", "")),
        technical_note=_text(value.get("기술적소견", "")),
        values={key: deepcopy(item) for key, item in value.items() if key not in known},
        criteria_results=criteria,
        photos=photos,
        raw=raw,
    )


def _photo_matches_item(photo: PhotoEntry, item: Mapping[str, Any]) -> bool:
    """Match only explicit item labels; generic equipment photos stay on target."""
    item_no = _text(item.get("번호", "")).strip()
    item_name = _text(item.get("점검내용", item.get("점검항목", ""))).strip()
    label = _text(photo.raw.get("점검항목", "")).strip()
    if not label or not item_name:
        return False
    return label == item_name or label == f"{item_no}. {item_name}"


def _system_review_entries(value: Any) -> list[SystemReviewEntry]:
    if not isinstance(value, Mapping):
        return []
    entries = []
    for category, section in value.items():
        if isinstance(section, list):
            for row in section:
                if not isinstance(row, Mapping):
                    continue
                entries.append(
                    SystemReviewEntry(
                        category=_text(category),
                        judgment=_text(
                            row.get("판정", row.get("검토결과", row.get("결과", "")))
                        ),
                        note=_text(row.get("비고", row.get("소견", row.get("내용", "")))),
                        values=_mapping(row),
                    )
                )
        elif isinstance(section, Mapping):
            entries.append(
                SystemReviewEntry(
                    category=_text(category),
                    judgment=_text(
                        section.get("판정", section.get("검토결과", section.get("결과", "")))
                    ),
                    note=_text(section.get("비고", section.get("소견", section.get("내용", "")))),
                    values=_mapping(section),
                )
            )
        else:
            entries.append(
                SystemReviewEntry(category=_text(category), values={"값": deepcopy(section)})
            )
    return entries


def build_report_document(project_data: Mapping[str, Any]) -> ReportDocument:
    """Create a detached report model from current or legacy project data."""
    if not isinstance(project_data, Mapping):
        raise TypeError("project_data must be a mapping")

    warnings: list[str] = []
    site_source = project_data.get("현장정보")
    if isinstance(site_source, Mapping):
        site = _mapping(site_source)
    else:
        # The historical site-information JSON is a flat site dictionary.
        site = _mapping(project_data)

    equipment_rows = _rows(project_data.get("장비대장", []))
    equipment = []
    equipment_by_id: dict[str, EquipmentEntry] = {}
    for raw in equipment_rows:
        entry = EquipmentEntry(
            equipment_id=_text(raw.get("equipment_id", "")).strip(),
            equipment_type=_text(raw.get("설비종류", "")),
            subtype=_text(raw.get("세부유형", "")),
            management_no=_text(raw.get("관리번호", "")),
            location=_text(raw.get("설치위치", "")),
            specification=_text(raw.get("주요사양", "")),
            installation_year=_text(raw.get("설치연도", "")),
            note=_text(raw.get("비고", "")),
            raw=raw,
        )
        equipment.append(entry)
        if entry.equipment_id:
            equipment_by_id.setdefault(entry.equipment_id, entry)

    result_map = project_data.get("설비별점검결과", {})
    result_map = result_map if isinstance(result_map, Mapping) else {}
    target_rows = _rows(project_data.get("점검대상선정", []))
    photo_rows = _rows(project_data.get("사진관리", []))
    photos_by_target: dict[str, list[PhotoEntry]] = {}
    for raw in photo_rows:
        key = _text(raw.get("장비키", ""))
        photos_by_target.setdefault(key, []).append(_photo(raw))

    targets = []
    consumed_keys = set()
    for target_row, raw in enumerate(target_rows):
        key = _target_key(raw, target_row)
        equipment_id = _text(raw.get("equipment_id", "")).strip()
        linked_equipment = equipment_by_id.get(equipment_id)
        if equipment_id and linked_equipment is None:
            warnings.append(f"점검대상 {key}: equipment_id 장비대장 매칭 실패")
        management_no = linked_equipment.management_no if linked_equipment else ""
        if not management_no:
            register_row = raw.get("장비대장행")
            if isinstance(register_row, int) and 0 <= register_row < len(equipment):
                candidate = equipment[register_row]
                if not equipment_id or candidate.equipment_id == equipment_id:
                    management_no = candidate.management_no
        item_rows = result_map.get(key, [])
        if not isinstance(item_rows, list):
            item_rows = []
        if key in result_map:
            consumed_keys.add(key)

        target_photos = []
        for photo in photos_by_target.get(key, []):
            photo.equipment_id = equipment_id
            target_photos.append(photo)
            if photo.file_path and not Path(photo.file_path).is_file():
                warnings.append(f"사진 파일 없음: {photo.file_path}")

        items = []
        for item in item_rows:
            if not isinstance(item, Mapping):
                continue
            item_equipment_id = _text(item.get("equipment_id", "")).strip()
            if item_equipment_id and equipment_id and item_equipment_id != equipment_id:
                warnings.append(
                    f"점검결과 {key} / {_text(item.get('번호', ''))}: equipment_id 불일치"
                )
            item_photos = [
                photo for photo in target_photos if _photo_matches_item(photo, item)
            ]
            items.append(_inspection_item(item, item_photos))
        target_label = " | ".join(
            part for part in (_text(raw.get("설비종류", "")), management_no) if part
        )
        targets.append(
            InspectionTargetSection(
                target_key=key,
                equipment_id=equipment_id,
                equipment_type=_text(raw.get("설비종류", "")),
                management_no_snapshot=management_no,
                target_label=target_label,
                inspection_items=items,
                photos=target_photos,
                raw=raw,
            )
        )

    for key in result_map:
        if key not in consumed_keys:
            warnings.append(f"점검결과 {key}: 현재 점검대상과 정확히 매칭되지 않음")

    calculations = []
    for raw in _rows(project_data.get("성능계산", [])):
        equipment_id = _text(raw.get("equipment_id", "")).strip()
        if equipment_id and equipment_id not in equipment_by_id:
            warnings.append(
                f"성능계산 {_text(raw.get('종류', ''))}: equipment_id 장비대장 매칭 실패"
            )
        calculations.append(
            CalculationEntry(
                equipment_id=equipment_id,
                calculation_type=_text(raw.get("종류", "")),
                inputs=deepcopy(raw.get("입력값", {})),
                outputs=deepcopy(raw.get("산출결과", {})),
                key_metric=_text(raw.get("핵심지표", "")),
                key_value=deepcopy(raw.get("핵심값", "")),
                reference_judgment=_text(raw.get("판정", "")),
                management_no_snapshot=_text(
                    raw.get("관리번호_snapshot", raw.get("장비번호", ""))
                ),
                raw=raw,
            )
        )

    energy_raw = _mapping(project_data.get("에너지분석", {}))
    yearly = energy_raw.get("에너지사용량", energy_raw.get("연도별사용량", []))
    comparisons = energy_raw.get("1차에너지분석", energy_raw.get("비교결과", []))
    energy = EnergyAnalysisSection(
        yearly_records=_rows(yearly),
        comparison_results=_rows(comparisons),
        notes={
            key: deepcopy(value)
            for key, value in energy_raw.items()
            if key not in {"에너지사용량", "연도별사용량", "1차에너지분석", "비교결과"}
        },
        raw=energy_raw,
    )

    previous_raw = project_data.get("전년도비교", {})
    previous_rows = (
        previous_raw.get("비교결과", [])
        if isinstance(previous_raw, Mapping)
        else previous_raw
    )

    improvements = []
    improvement_raw = project_data.get("성능개선계획", {})
    if isinstance(improvement_raw, Mapping):
        for section, rows in improvement_raw.items():
            for row in _rows(rows):
                improvements.append(ImprovementPlanEntry(_text(section), row))
    elif isinstance(improvement_raw, list):
        improvements = [ImprovementPlanEntry("", row) for row in _rows(improvement_raw)]

    summary = {
        "source_project_version": _text(project_data.get("프로그램버전", "")),
        "equipment_count": len(equipment),
        "target_count": len(targets),
        "inspection_item_count": sum(len(target.inspection_items) for target in targets),
        "photo_count": len(photo_rows),
        "calculation_count": len(calculations),
    }
    return ReportDocument(
        report_version=REPORT_MODEL_VERSION,
        site=SiteSection(site),
        inspection_summary=summary,
        engineers=[EngineerEntry(row) for row in _rows(project_data.get("참여기술자", []))],
        equipment=equipment,
        targets=targets,
        system_reviews=_system_review_entries(project_data.get("시스템검토", {})),
        performance_calculations=calculations,
        energy_analysis=energy,
        previous_year_comparison=[PreviousComparisonEntry(row) for row in _rows(previous_rows)],
        root_cause_analysis=[RootCauseEntry(row) for row in _rows(project_data.get("원인분석", []))],
        improvement_plans=improvements,
        report_warnings=warnings,
    )
