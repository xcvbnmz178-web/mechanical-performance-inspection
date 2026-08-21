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
class ProductionReportView:
    site: ProductionSiteView = field(default_factory=ProductionSiteView)
    company: ProductionCompanyView = field(default_factory=ProductionCompanyView)
    result_rows: tuple[ProductionResultSummaryRow, ...] = ()
    first_target: ProductionTargetView | None = None
    warnings: tuple[str, ...] = ()
    targets: tuple[ProductionTargetView, ...] = ()
