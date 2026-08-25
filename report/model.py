"""Output-format-independent read models for performance inspection reports."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SiteSection:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class EngineerEntry:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class EquipmentEntry:
    equipment_id: str = ""
    equipment_type: str = ""
    subtype: str = ""
    management_no: str = ""
    location: str = ""
    specification: str = ""
    installation_year: str = ""
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CriterionExecution:
    criterion_index: int | None = None
    criterion_name: str = ""
    performed_methods: list[str] = field(default_factory=list)
    inspection_status: str = ""
    criterion_judgment: str = ""
    unavailable_reason: str = ""
    substitution: dict[str, Any] = field(default_factory=dict)
    evidence_note: str = ""


@dataclass
class PhotoEntry:
    equipment_id: str = ""
    target_key: str = ""
    item_no: str = ""
    file_path: str = ""
    caption: str = ""
    category: str = ""
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class InspectionItemResult:
    item_no: str = ""
    item_name: str = ""
    inspection_method: str = ""
    inspection_criteria: str = ""
    measured_value: Any = ""
    design_value: Any = ""
    rated_value: Any = ""
    judgment: str = ""
    technical_note: str = ""
    values: dict[str, Any] = field(default_factory=dict)
    criteria_results: list[CriterionExecution] = field(default_factory=list)
    photos: list[PhotoEntry] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class InspectionTargetSection:
    target_key: str = ""
    equipment_id: str = ""
    equipment_type: str = ""
    management_no_snapshot: str = ""
    target_label: str = ""
    inspection_items: list[InspectionItemResult] = field(default_factory=list)
    photos: list[PhotoEntry] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemReviewEntry:
    category: str = ""
    judgment: str = ""
    note: str = ""
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class CalculationEntry:
    equipment_id: str = ""
    calculation_type: str = ""
    inputs: Any = field(default_factory=dict)
    outputs: Any = field(default_factory=dict)
    key_metric: str = ""
    key_value: Any = ""
    reference_judgment: str = ""
    management_no_snapshot: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class EnergyAnalysisSection:
    yearly_records: list[dict[str, Any]] = field(default_factory=list)
    comparison_results: list[dict[str, Any]] = field(default_factory=list)
    notes: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgingAnalysisSection:
    rows: list[dict[str, Any]] = field(default_factory=list)
    reference_source: str = ""
    overall_opinion: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreviousComparisonEntry:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class RootCauseEntry:
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImprovementPlanEntry:
    section: str = ""
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReportDocument:
    report_version: str = "1.0"
    site: SiteSection = field(default_factory=SiteSection)
    inspection_summary: dict[str, Any] = field(default_factory=dict)
    engineers: list[EngineerEntry] = field(default_factory=list)
    equipment: list[EquipmentEntry] = field(default_factory=list)
    targets: list[InspectionTargetSection] = field(default_factory=list)
    system_reviews: list[SystemReviewEntry] = field(default_factory=list)
    performance_calculations: list[CalculationEntry] = field(default_factory=list)
    energy_analysis: EnergyAnalysisSection = field(
        default_factory=EnergyAnalysisSection
    )
    aging_analysis: AgingAnalysisSection = field(
        default_factory=AgingAnalysisSection
    )
    previous_year_comparison: list[PreviousComparisonEntry] = field(
        default_factory=list
    )
    root_cause_analysis: list[RootCauseEntry] = field(default_factory=list)
    improvement_plans: list[ImprovementPlanEntry] = field(default_factory=list)
    report_warnings: list[str] = field(default_factory=list)


def report_document_to_dict(document: ReportDocument) -> dict[str, Any]:
    """Return a deterministic plain-data snapshot; it is not project storage."""
    if not isinstance(document, ReportDocument):
        raise TypeError("document must be a ReportDocument")
    return asdict(document)
