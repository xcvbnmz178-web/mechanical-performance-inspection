"""Customer-facing read models for the production HWP report."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProductionSiteView:
    site_name: str = ""
    address: str = ""
    management_entity: str = ""
    building_use: str = ""
    total_floor_area: str = ""
    inspection_period: str = ""
    report_date: str = ""


@dataclass(frozen=True)
class ProductionCompanyView:
    company_name: str = "TEST 성능점검업체"
    introduction: str = "회사정보 로컬 설정이 필요합니다."
    address: str = ""
    telephone: str = ""
    fax: str = ""
    email: str = ""
    registration_no: str = ""
    responsible_engineer: str = ""


@dataclass(frozen=True)
class ProductionPhotoView:
    file_path: str = ""
    caption: str = ""


@dataclass(frozen=True)
class ProductionInspectionItemView:
    item_no: str = ""
    item_name: str = ""
    inspection_method: str = ""
    inspection_criteria: str = ""
    reference_value: str = ""
    measured_value: str = ""
    judgment: str = ""
    technical_note: str = ""
    photos: tuple[ProductionPhotoView, ...] = ()


@dataclass(frozen=True)
class ProductionTargetView:
    equipment_type: str = ""
    management_no: str = ""
    location: str = ""
    specification: str = ""
    target_label: str = ""
    items: tuple[ProductionInspectionItemView, ...] = ()
    overview_photo: ProductionPhotoView | None = None


@dataclass(frozen=True)
class ProductionResultSummaryRow:
    equipment_type: str = ""
    management_no: str = ""
    judgment_summary: str = ""
    action_note: str = ""


@dataclass(frozen=True)
class ProductionSystemReviewSummaryRow:
    review_item: str = ""
    detail: str = ""
    standard: str = ""
    result: str = ""


@dataclass(frozen=True)
class ProductionDocumentReviewRow:
    document_name: str = ""
    status: str = ""
    engineer_note: str = ""
    remark: str = ""


@dataclass(frozen=True)
class ProductionOperationReviewRow:
    review_type: str = ""
    category: str = ""
    equipment_name: str = ""
    result: str = ""
    basis: str = ""
    remark: str = ""


@dataclass(frozen=True)
class ProductionSystemReviewView:
    summary_rows: tuple[ProductionSystemReviewSummaryRow, ...] = ()
    document_rows: tuple[ProductionDocumentReviewRow, ...] = ()
    operation_rows: tuple[ProductionOperationReviewRow, ...] = ()
    status: str = "자료없음"


@dataclass(frozen=True)
class ProductionAgingRow:
    category: str = ""
    equipment_type: str = ""
    management_no: str = ""
    installation_year: str = ""
    reference_lifespan: str = ""
    elapsed_years: str = ""
    aging_status: str = ""
    reference_source: str = ""
    note: str = ""


@dataclass(frozen=True)
class ProductionAgingView:
    rows: tuple[ProductionAgingRow, ...] = ()
    reference_source: str = ""
    overall_opinion: str = ""
    status: str = "자료없음"


@dataclass(frozen=True)
class ProductionImprovementRow:
    section: str = ""
    category: str = ""
    equipment_type: str = ""
    target_label: str = ""
    issue: str = ""
    action: str = ""
    schedule: str = ""
    status: str = ""


@dataclass(frozen=True)
class ProductionImprovementView:
    rows: tuple[ProductionImprovementRow, ...] = ()
    status: str = "자료없음"


@dataclass(frozen=True)
class ProductionReportView:
    site: ProductionSiteView = field(default_factory=ProductionSiteView)
    company: ProductionCompanyView = field(default_factory=ProductionCompanyView)
    result_rows: tuple[ProductionResultSummaryRow, ...] = ()
    first_target: ProductionTargetView | None = None
    warnings: tuple[str, ...] = ()
    targets: tuple[ProductionTargetView, ...] = ()
    system_review: ProductionSystemReviewView = field(
        default_factory=ProductionSystemReviewView
    )
    aging: ProductionAgingView = field(default_factory=ProductionAgingView)
    improvements: ProductionImprovementView = field(
        default_factory=ProductionImprovementView
    )
