"""Explicit field contracts between ReportDocument and report templates."""

from dataclasses import dataclass, field
from typing import Any, Mapping

from .model import ReportDocument


TEMPLATE_ID_FIELD = "TEMPLATE_ID"
TEMPLATE_VERSION_FIELD = "TEMPLATE_VERSION"


@dataclass(frozen=True)
class FieldContract:
    field_name: str
    source_path: str
    required: bool = False
    formatter: str = "text"
    max_length: int | None = None
    note: str = ""


@dataclass(frozen=True)
class RepeatColumnContract:
    header: str
    source_path: str
    formatter: str = "text"


@dataclass(frozen=True)
class RepeatSectionContract:
    section_name: str
    marker_start: str
    marker_end: str = ""
    source_path: str = "targets"
    item_template: tuple[RepeatColumnContract, ...] = ()
    required: bool = True
    page_break_between: bool = True
    note: str = ""


@dataclass(frozen=True)
class TemplateContract:
    template_id: str
    template_version: str
    required_fields: tuple[FieldContract, ...] = ()
    optional_fields: tuple[FieldContract, ...] = ()
    repeat_sections: tuple[RepeatSectionContract, ...] = ()
    photo_slots: tuple[str, ...] = ()
    supported_report_versions: tuple[str, ...] = ("1.0",)

    @property
    def fields(self) -> tuple[FieldContract, ...]:
        return self.required_fields + self.optional_fields


@dataclass
class ContractValidationResult:
    values: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    information: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors


def _resolve_path(root: Any, source_path: str) -> Any:
    current = root
    for part in source_path.split("."):
        if isinstance(current, Mapping):
            current = current.get(part, "")
        else:
            current = getattr(current, part, "")
    return current


def _format_text(value: Any) -> str:
    return "" if value is None else str(value)


def _format_inspection_period(value: Any) -> str:
    if not isinstance(value, Mapping):
        return ""
    start = _format_text(value.get("점검시작일", "")).strip()
    end = _format_text(value.get("점검종료일", "")).strip()
    if start and end:
        return start if start == end else f"{start} ~ {end}"
    return start or end


FORMATTERS = {
    "text": _format_text,
    "inspection_period": _format_inspection_period,
}


def resolve_field_value(document: ReportDocument, contract: FieldContract) -> str:
    if contract.formatter not in FORMATTERS:
        raise ValueError(f"지원하지 않는 formatter: {contract.formatter}")
    value = FORMATTERS[contract.formatter](
        _resolve_path(document, contract.source_path)
    )
    if contract.max_length is not None:
        value = value[: contract.max_length]
    return value


def validate_template_contract(
    document: ReportDocument,
    contract: TemplateContract,
    available_fields: set[str] | list[str] | tuple[str, ...],
    template_metadata: Mapping[str, str] | None = None,
) -> ContractValidationResult:
    """Validate field presence, source values, and optional template identity."""
    result = ContractValidationResult()
    available = {str(name).strip() for name in available_fields if str(name).strip()}

    if document.report_version not in contract.supported_report_versions:
        result.errors.append(
            "지원하지 않는 ReportDocument 버전: "
            f"{document.report_version} (지원: {', '.join(contract.supported_report_versions)})"
        )

    for field_contract in contract.fields:
        present = field_contract.field_name in available
        if not present:
            message = f"템플릿 필드 없음: {field_contract.field_name}"
            if field_contract.required:
                result.errors.append(message)
            else:
                result.warnings.append(message)
            continue
        try:
            value = resolve_field_value(document, field_contract)
        except ValueError as error:
            result.errors.append(str(error))
            continue
        result.values[field_contract.field_name] = value
        if not value.strip():
            message = f"보고서 데이터 없음: {field_contract.field_name}"
            if field_contract.required:
                result.errors.append(message)
            else:
                result.warnings.append(message)

    known = {item.field_name for item in contract.fields}
    for section in contract.repeat_sections:
        for marker in (section.marker_start, section.marker_end):
            if not marker:
                continue
            known.add(marker)
            if marker not in available:
                message = f"반복 섹션 anchor 없음: {section.section_name} / {marker}"
                if section.required:
                    result.errors.append(message)
                else:
                    result.warnings.append(message)
    known.update({TEMPLATE_ID_FIELD, TEMPLATE_VERSION_FIELD})
    extras = sorted(available - known)
    if extras:
        result.information.append("계약 외 템플릿 필드: " + ", ".join(extras))

    metadata = dict(template_metadata or {})
    template_id = str(metadata.get(TEMPLATE_ID_FIELD, "")).strip()
    template_version = str(metadata.get(TEMPLATE_VERSION_FIELD, "")).strip()
    if template_id and template_id != contract.template_id:
        result.errors.append(
            f"템플릿 ID 불일치: {template_id} != {contract.template_id}"
        )
    if template_version and template_version != contract.template_version:
        result.errors.append(
            "템플릿 버전 불일치: "
            f"{template_version} != {contract.template_version}"
        )
    if not template_id or not template_version:
        result.warnings.append(
            "템플릿 ID/버전 예약 필드가 없어 파일 내부 버전을 확인하지 못함"
        )
    return result


MINIMAL_HWP_CONTRACT = TemplateContract(
    template_id="PERFORMANCE_INSPECTION_MINIMAL",
    template_version="1.0",
    required_fields=(
        FieldContract("SITE_NAME", "site.values.현장명", True, note="현장명"),
        FieldContract("SITE_ADDRESS", "site.values.주소", True, note="주소"),
        FieldContract(
            "MANAGEMENT_ENTITY", "site.values.관리주체", True, note="관리주체"
        ),
        FieldContract(
            "INSPECTION_PERIOD",
            "site.values",
            True,
            formatter="inspection_period",
            note="점검시작일과 점검종료일",
        ),
        FieldContract(
            "REPORT_DATE", "site.values.보고서작성일", True, note="보고서 작성일"
        ),
    ),
    optional_fields=(
        FieldContract("SITE_USE", "site.values.용도", False, note="건축물 용도"),
    ),
)


TARGET_ITEM_COLUMNS = (
    RepeatColumnContract("번호", "item_no"),
    RepeatColumnContract("점검항목", "item_name"),
    RepeatColumnContract("점검방법", "inspection_method"),
    RepeatColumnContract("점검기준", "inspection_criteria"),
    RepeatColumnContract("측정/확인값", "measured_value"),
    RepeatColumnContract("최종판정", "judgment"),
    RepeatColumnContract("기술적소견", "technical_note"),
)


TARGET_REPEAT_SECTION = RepeatSectionContract(
    section_name="INSPECTION_TARGETS",
    marker_start="TARGETS_REPEAT_ANCHOR",
    source_path="targets",
    item_template=TARGET_ITEM_COLUMNS,
    required=True,
    page_break_between=True,
    note="InspectionTargetSection별 설비 헤더와 가변 점검항목 표",
)


MINIMAL_REPEAT_HWP_CONTRACT = TemplateContract(
    template_id="PERFORMANCE_INSPECTION_REPEAT_MINIMAL",
    template_version="1.0",
    required_fields=MINIMAL_HWP_CONTRACT.required_fields,
    optional_fields=MINIMAL_HWP_CONTRACT.optional_fields,
    repeat_sections=(TARGET_REPEAT_SECTION,),
    supported_report_versions=MINIMAL_HWP_CONTRACT.supported_report_versions,
)
