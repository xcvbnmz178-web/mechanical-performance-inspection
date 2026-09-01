"""Map ReportDocument to customer-visible production report values."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

from .model import InspectionItemResult, InspectionTargetSection, PhotoEntry, ReportDocument
from .production_model import (
    ProductionAgingRow,
    ProductionAgingView,
    ProductionCompanyView,
    ProductionDocumentReviewRow,
    ProductionImprovementRow,
    ProductionImprovementView,
    ProductionInspectionItemView,
    ProductionOperationReviewRow,
    ProductionPhotoView,
    ProductionReportView,
    ProductionResultSummaryRow,
    ProductionSiteView,
    ProductionSystemReviewSummaryRow,
    ProductionSystemReviewView,
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


def _photo_path_key(file_path: str) -> str:
    return str(Path(file_path).resolve()).casefold()


def _select_photos(
    document: ReportDocument,
    target: InspectionTargetSection,
    item: InspectionItemResult | None,
    limit: int,
    used_photo_paths: set[str] | None = None,
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
    selected_paths = set(used_photo_paths or ())
    for photo in exact:
        if not _existing_photo(photo):
            continue
        path_key = _photo_path_key(photo.file_path)
        if path_key in selected_paths:
            continue
        selected.append(ProductionPhotoView(photo.file_path, photo.caption or photo.note))
        selected_paths.add(path_key)
        if len(selected) >= limit:
            break
    return tuple(selected)


def _item_view(
    document: ReportDocument,
    target: InspectionTargetSection,
    item: InspectionItemResult,
    used_photo_paths: set[str],
) -> ProductionInspectionItemView:
    photos = _select_photos(document, target, item, 2, used_photo_paths)
    used_photo_paths.update(_photo_path_key(photo.file_path) for photo in photos)
    return ProductionInspectionItemView(
        item_no=item.item_no,
        item_name=item.item_name,
        inspection_method=item.inspection_method,
        inspection_criteria=item.inspection_criteria,
        reference_value=_reference_value(item),
        measured_value=_text(item.measured_value),
        judgment=item.judgment,
        technical_note=item.technical_note,
        photos=photos,
    )


def _target_view(document: ReportDocument, target: InspectionTargetSection) -> ProductionTargetView:
    equipment = next(
        (entry for entry in document.equipment if target.equipment_id and entry.equipment_id == target.equipment_id),
        None,
    )
    overview = _select_photos(document, target, None, 1)
    used_photo_paths = {_photo_path_key(photo.file_path) for photo in overview}
    items = tuple(
        _item_view(document, target, item, used_photo_paths)
        for item in target.inspection_items
    )
    return ProductionTargetView(
        equipment_type=target.equipment_type,
        management_no=target.management_no_snapshot,
        location=equipment.location if equipment else "",
        specification=equipment.specification if equipment else "",
        target_label=target.target_label,
        items=items,
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


def _review_result(value) -> str:
    return _text(value) or "확인필요"


def _system_review_view(document: ReportDocument) -> ProductionSystemReviewView:
    summary_rows = []
    document_rows = []
    operation_rows = []
    for entry in document.system_reviews:
        values = entry.values
        if entry.category == "검토사항총괄":
            summary_rows.append(
                ProductionSystemReviewSummaryRow(
                    review_item=_text(values.get("점검항목", "")),
                    detail=_text(values.get("세부검토사항", "")),
                    standard=_text(values.get("고정검토기준", "")),
                    result=_review_result(values.get("결과요약", entry.judgment)),
                )
            )
        elif entry.category == "유지관리지침서":
            document_rows.append(
                ProductionDocumentReviewRow(
                    document_name=_text(values.get("구비서류", "")),
                    status=_review_result(values.get("보유상태", entry.judgment)),
                    engineer_note=_text(values.get("책임기술자소견", "")),
                    remark=_text(values.get("비고", entry.note)),
                )
            )
        elif entry.category in {"시스템작동상태", "설계측정값일치"}:
            operation_rows.append(
                ProductionOperationReviewRow(
                    review_type=(
                        "작동상태" if entry.category == "시스템작동상태"
                        else "설계·측정값"
                    ),
                    category=_text(values.get("구분", "")),
                    equipment_name=_text(values.get("대상설비", "")),
                    result=_review_result(values.get("점검결과", entry.judgment)),
                    basis=_text(values.get("비교근거", "")),
                    remark=_text(values.get("비고", entry.note)),
                )
            )
    all_rows = summary_rows or document_rows or operation_rows
    results = [row.result for row in summary_rows] + [row.status for row in document_rows]
    results += [row.result for row in operation_rows]
    status = "자료없음" if not all_rows else (
        "확인필요" if any(value == "확인필요" for value in results) else "검토완료"
    )
    return ProductionSystemReviewView(
        tuple(summary_rows), tuple(document_rows), tuple(operation_rows), status
    )


def _aging_view(document: ReportDocument) -> ProductionAgingView:
    rows = tuple(
        ProductionAgingRow(
            category=_text(value.get("구분", "")),
            equipment_type=_text(value.get("대상설비", "")),
            management_no=_text(value.get("장비번호계통명", "")),
            installation_year=_text(value.get("설치연도", "")),
            reference_lifespan=_text(
                value.get("참고내용연수")
                if str(value.get("참고내용연수") or "").strip()
                else value.get("내구연한", "")
            ),
            elapsed_years=_text(value.get("사용연수", "")),
            aging_status=_review_result(value.get("노후도", "")),
            reference_source=_text(value.get("적용근거", "")),
            note=_text(value.get("비고", "")),
        )
        for value in document.aging_analysis.rows
    )
    status = "자료없음" if not rows else (
        "확인필요" if any(row.aging_status == "확인필요" for row in rows)
        else "검토완료"
    )
    return ProductionAgingView(
        rows=rows,
        reference_source=_text(document.aging_analysis.reference_source),
        overall_opinion=_text(document.aging_analysis.overall_opinion),
        status=status,
    )


def _target_label_for_values(values: Mapping, targets) -> str:
    equipment_type = _first(values, "대상설비", "설비종류")
    management_no = _first(
        values, "장비번호계통명", "관리번호", "장비번호"
    )
    if "|" in equipment_type:
        parts = [part.strip() for part in equipment_type.split("|") if part.strip()]
        equipment_type = parts[0] if parts else equipment_type
        if len(parts) > 1 and not management_no:
            management_no = parts[1]
    candidates = [
        target for target in targets
        if not equipment_type or target.equipment_type == equipment_type
    ]
    if management_no:
        exact = [target for target in candidates if target.management_no == management_no]
        if len(exact) == 1:
            return exact[0].target_label or " | ".join(
                part for part in (exact[0].equipment_type, exact[0].management_no) if part
            )
    if len(candidates) == 1:
        target = candidates[0]
        return target.target_label or " | ".join(
            part for part in (target.equipment_type, target.management_no) if part
        )
    unresolved = " | ".join(
        part for part in (equipment_type, management_no) if part
    )
    return f"{unresolved} (대상 확인필요)" if unresolved else "확인필요"


def _improvement_view(document: ReportDocument, targets) -> ProductionImprovementView:
    rows = []
    matched_labels = set()
    for entry in document.improvement_plans:
        values = entry.values
        target_label = _target_label_for_values(values, targets)
        matched_labels.add(target_label)
        if entry.section == "5개년개선계획":
            schedule_parts = [
                f"{year}: {_text(values.get(year, ''))}"
                for year in ("1년차", "2년차", "3년차", "4년차", "5년차")
                if _text(values.get(year, "")) not in {"", "-"}
            ]
            issue = _text(values.get("성능개선 필요성", ""))
            action = ""
            status = "계획수립" if schedule_parts else "해당없음"
        else:
            issue = _text(values.get("부적합사항", ""))
            action = _text(values.get("개선사항", ""))
            schedule_parts = []
            status = "조치필요" if action not in {"", "-"} else "해당없음"
        rows.append(
            ProductionImprovementRow(
                section=entry.section,
                category=_text(values.get("구분", "")),
                equipment_type=_text(values.get("대상설비", "")),
                target_label=target_label,
                issue=issue or "자료없음",
                action=(action or "자료없음") if entry.section != "5개년개선계획" else "연도별 계획 참조",
                schedule=" / ".join(schedule_parts),
                status=status,
            )
        )

    for root_cause in document.root_cause_analysis:
        values = root_cause.values
        action = _text(values.get("개선방안", ""))
        if not action:
            continue
        target_label = _target_label_for_values(values, targets)
        if target_label in matched_labels:
            continue
        rows.append(
            ProductionImprovementRow(
                section="원인분석",
                equipment_type=_text(values.get("대상설비", "")),
                target_label=target_label,
                issue=_first(values, "이상현상", "점검항목") or "확인필요",
                action=action,
                status="조치필요",
            )
        )
        matched_labels.add(target_label)

    status = "자료없음" if not rows else (
        "확인필요" if any("확인필요" in row.target_label for row in rows)
        else "계획수립"
    )
    return ProductionImprovementView(tuple(rows), status)


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
    targets = tuple(_target_view(document, target) for target in document.targets)
    for target in targets:
        assert_summary_detail_consistency(target.items)
    first_target = targets[0] if targets else None
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
    for target_index, target in enumerate(targets, 1):
        if not target.items:
            warnings.append(f"점검대상 {target_index}: 출력할 점검항목이 없음")
    system_review = _system_review_view(document)
    aging = _aging_view(document)
    improvements = _improvement_view(document, targets)
    return ProductionReportView(
        site=site,
        company=company,
        result_rows=tuple(result_rows),
        first_target=first_target,
        warnings=tuple(warnings),
        targets=targets,
        system_review=system_review,
        aging=aging,
        improvements=improvements,
    )


def customer_visible_text(view: ProductionReportView) -> str:
    """Flatten only customer-visible values for leakage tests."""
    values = [
        view.site.site_name, view.site.address, view.site.management_entity,
        view.company.company_name, view.company.introduction,
    ]
    for row in view.result_rows:
        values.extend((row.equipment_type, row.management_no, row.judgment_summary, row.action_note))
    for target in view.targets:
        values.extend((target.equipment_type, target.management_no))
        if target.overview_photo:
            values.append(target.overview_photo.caption)
        for item in target.items:
            values.extend((
                item.item_no, item.item_name, item.inspection_method,
                item.inspection_criteria, item.reference_value, item.measured_value,
                item.judgment, item.technical_note,
            ))
            values.extend(photo.caption for photo in item.photos)
    for row in view.system_review.summary_rows:
        values.extend((row.review_item, row.detail, row.standard, row.result))
    for row in view.system_review.document_rows:
        values.extend((row.document_name, row.status, row.engineer_note, row.remark))
    for row in view.system_review.operation_rows:
        values.extend((row.review_type, row.category, row.equipment_name, row.result, row.basis, row.remark))
    for row in view.aging.rows:
        values.extend((
            row.category, row.equipment_type, row.management_no,
            row.installation_year, row.reference_lifespan, row.elapsed_years,
            row.aging_status, row.reference_source, row.note,
        ))
    values.extend((view.aging.reference_source, view.aging.overall_opinion))
    for row in view.improvements.rows:
        values.extend((
            row.section, row.category, row.equipment_type, row.target_label,
            row.issue, row.action, row.schedule, row.status,
        ))
    return "\n".join(_text(value) for value in values)


def validate_customer_visible_text(view: ProductionReportView) -> None:
    text = customer_visible_text(view)
    found = [token for token in FORBIDDEN_CUSTOMER_TOKENS if token.lower() in text.lower()]
    if found:
        raise ValueError(f"고객용 보고서 금지 문자열 발견: {', '.join(found)}")
