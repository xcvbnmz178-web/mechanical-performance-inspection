"""Orchestrate project data -> ReportDocument -> production HWP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .hwp_production_renderer import HwpProductionRenderer, ProductionHwpResult
from .production_model import ProductionCompanyView, ProductionReportView
from .production_view import build_production_report_view
from .service import build_report_document


def load_local_company_profile(path: str | Path | None) -> ProductionCompanyView | None:
    if not path:
        return None
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"회사정보 로컬 파일이 없습니다: {source}")
    with source.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, Mapping):
        raise ValueError("회사정보 로컬 파일은 JSON 객체여야 합니다")
    return ProductionCompanyView(
        company_name=str(data.get("company_name", "") or ""),
        introduction=str(data.get("introduction", "") or ""),
        address=str(data.get("address", "") or ""),
        telephone=str(data.get("telephone", "") or ""),
        fax=str(data.get("fax", "") or ""),
        email=str(data.get("email", "") or ""),
        registration_no=str(data.get("registration_no", "") or ""),
        responsible_engineer=str(data.get("responsible_engineer", "") or ""),
    )


def prepare_production_report(
    project_data: Mapping[str, Any],
    *,
    company_profile_path: str | Path | None = None,
) -> ProductionReportView:
    document = build_report_document(project_data)
    company = load_local_company_profile(company_profile_path)
    return build_production_report_view(document, company)


def generate_production_hwp(
    project_data: Mapping[str, Any],
    output_path: str | Path,
    *,
    company_profile_path: str | Path | None = None,
    pdf_preview_path: str | Path | None = None,
    renderer: HwpProductionRenderer | None = None,
    visible: bool = False,
) -> ProductionHwpResult:
    view = prepare_production_report(
        project_data, company_profile_path=company_profile_path
    )
    return (renderer or HwpProductionRenderer()).generate(
        view,
        output_path,
        visible=visible,
        pdf_preview_path=pdf_preview_path,
    )
