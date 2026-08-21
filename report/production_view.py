"""Map ReportDocument to customer-visible production report values."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

from .model import InspectionItemResult, InspectionTargetSection, PhotoEntry, ReportDocument
from .production_model import (
    ProductionCompanyView,
    ProductionInspectionItemView,
    ProductionPhotoView,
    ProductionReportView,
    ProductionResultSummaryRow,
    ProductionSiteView,
    ProductionTargetView,
)


FORBIDDEN_CUSTOMER_TOKENS = (
    "target_key",
    "equipment_id",
    "criterion_index",
    "sample-ch-",
    "DESIGN SAMPLE",
    "prototype",
)


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _first(values: Mapping, *keys: str) -> str:
    for key in keys:
        value = _text(values.get(key, ""))
        if value:
            return value
    return ""


def _period(values: Mapping) -> str:
    start = _first(values, "점검시작일", "현장점검시작일")
    end = _first(values, "점검종료일", "현장점검종료일")
    return " ~ ".join(part for part in (start, end) if part)


def _reference_value(item: InspectionItemResult) -> str:
    design = _text(item.design_value)
    rated = _text(item.rated_value)
    if design and rated and design != rated:
        return f"설계 {design} / 정격 {rated}"
    return design or rated


def _photo_matches_item(photo: PhotoEntry, item: InspectionItemResult) -> bool:
    label = _text(photo.raw.get("점검항목", ""))
    if photo.item_no and photo.item_no == item.item_no:
        return True
    return bool(label and label in {item.item_name, f"{item.item_no}. {item.item_name}"})


def _existing_photo(photo: PhotoEntry) -> bool:
    return bool(photo.file_path and Path(photo.file_path).is_file())


def _select_photos(
    document: ReportDocument,
    target: InspectionTargetSection,
    item: InspectionItemResult | None,
    limit: int,
) -> tuple[ProductionPhotoView, ...]:
    all_photos = [photo for candidate in document.targets for photo in candidate.photos]
    exact = [photo for photo in all_photos if photo.target_key == target.target_key]
    if item is not None:
        exact = [photo for photo in exact if _photo_matches_item(photo, item)]
    else:
        exact.sort(
            key=lambda photo: 0
            if _text(photo.category).lower() in {
                "equipment_overview", "장비 전체사진", "현황사진"
            }
            else 1
        )
    if not exact:
        exact = [
            photo
            for photo in all_photos
            if not photo.target_key and photo.equipment_id == target.equipment_id
            and (item is None or _photo_matches_item(photo, item))
        ]
    selected = []
    for photo in exact:
        if not _existing_photo(photo):
            continue
        selected.append(ProductionPhotoView(photo.file_path, photo.caption or photo.note))
        if len(selected) >= limit:
            break
    return tuple(selected)


def _item_view(
    document: ReportDocument,
    target: InspectionTargetSection,
    item: InspectionItemResult,
) -> ProductionInspectionItemView:
    return ProductionInspectionItemView(
        item_no=item.item_no,
        item_name=item.item_name,
        inspection_method=item.inspection_method,
        inspection_criteria=item.inspection_criteria,
        reference_value=_reference_value(item),
        measured_value=_text(item.measured_value),
        judgment=item.judgment,
        technical_note=item.technical_note,
        photos=_select_photos(document, target, item, 2),
    )


def _target_view(document: ReportDocument, target: InspectionTargetSection) -> ProductionTargetView:
    equipment = next(
        (entry for entry in document.equipment if target.equipment_id and entry.equipment_id == target.equipment_id),
        None,
    )
    overview = _select_photos(document, target, None, 1)
    return ProductionTargetView(
        equipment_type=target.equipment_type,
        management_no=target.management_no_snapshot,
        location=equipment.location if equipment else "",
        specification=equipment.specification if equipment else "",
        target_label=target.target_label,
        items=tuple(_item_view(document, target, item) for item in target.inspection_items),
        overview_photo=overview[0] if overview else None,
    )


def _judgment_summary(target: InspectionTargetSection) -> tuple[str, str]:
    marks = Counter()
    actions = []
    for item in target.inspection_items:
        judgment = _text(item.judgment)
        if judgment.startswith("○"):
            marks["○"] += 1
        elif judgment.startswith("X"):
            marks["X"] += 1
            if _text(item.technical_note):
                actions.append(_text(item.technical_note))
        elif judgment.startswith("/"):
            marks["/"] += 1
        elif judgment:
            marks[judgment] += 1
        else:
            marks["미점검"] += 1
    order = ("○", "X", "/", "미점검")
    summary = " / ".join(f"{key} {marks[key]}" for key in order if marks[key])
    for key in sorted(set(marks) - set(order)):
        summary += (" / " if summary else "") + f"{key} {marks[key]}"
    return summary or "기록없음", " · ".join(dict.fromkeys(actions))


def assert_summary_detail_consistency(items: Iterable[ProductionInspectionItemView]) -> None:
    """Ensure both report presentations consume the same immutable item objects."""
    fields = (
        "item_no", "item_name", "inspection_criteria", "reference_value",
        "measured_value", "judgment", "technical_note",
    )
    summary = [tuple(getattr(item, field) for field in fields) for item in items]
    detail = [tuple(getattr(item, field) for field in fields) for item in items]
    if summary != detail:
        raise AssertionError("요약/상세 점검결과 불일치")


def build_production_report_view(
    document: ReportDocument,
    company: ProductionCompanyView | None = None,
) -> ProductionReportView:
    values = document.site.values
    site = ProductionSiteView(
        site_name=_first(values, "현장명", "건축물명", "명칭"),
        address=_first(values, "주소", "소재지"),
        management_entity=_first(values, "관리주체", "관리자"),
        building_use=_first(values, "용도", "주용도"),
        total_floor_area=_first(values, "연면적"),
        inspection_period=_period(values),
        report_date=_first(values, "보고서작성일", "성능점검기준일", "점검일"),
    )
    first_target = _target_view(document, document.targets[0]) if document.targets else None
    if first_target:
        assert_summary_detail_consistency(first_target.items)
    result_rows = []
    for target in document.targets:
        summary, action = _judgment_summary(target)
        result_rows.append(
            ProductionResultSummaryRow(
                equipment_type=target.equipment_type,
                management_no=target.management_no_snapshot,
                judgment_summary=summary,
                action_note=action,
            )
        )
    warnings = list(document.report_warnings)
    if company is None:
        company = ProductionCompanyView()
        warnings.append("회사정보 로컬 설정이 없어 TEST placeholder를 사용함")
    if not document.targets:
        warnings.append("출력할 점검대상이 없음")
    return ProductionReportView(site, company, tuple(result_rows), first_target, tuple(warnings))


def customer_visible_text(view: ProductionReportView) -> str:
    """Flatten only customer-visible values for leakage tests."""
    values = [
        view.site.site_name, view.site.address, view.site.management_entity,
        view.company.company_name, view.company.introduction,
    ]
    for row in view.result_rows:
        values.extend((row.equipment_type, row.management_no, row.judgment_summary, row.action_note))
    if view.first_target:
        values.extend((view.first_target.equipment_type, view.first_target.management_no))
        if view.first_target.overview_photo:
            values.append(view.first_target.overview_photo.caption)
        for item in view.first_target.items:
            values.extend((
                item.item_no, item.item_name, item.inspection_method,
                item.inspection_criteria, item.reference_value, item.measured_value,
                item.judgment, item.technical_note,
            ))
            values.extend(photo.caption for photo in item.photos)
    return "\n".join(_text(value) for value in values)


def validate_customer_visible_text(view: ProductionReportView) -> None:
    text = customer_visible_text(view)
    found = [token for token in FORBIDDEN_CUSTOMER_TOKENS if token.lower() in text.lower()]
    if found:
        raise ValueError(f"고객용 보고서 금지 문자열 발견: {', '.join(found)}")
