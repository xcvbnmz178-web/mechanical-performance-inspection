"""Orchestrate project data -> ReportDocument -> production HWP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .hwp_adapter import HwpComUnavailableError
from .hwp_production_renderer import (
    HwpProductionRenderer,
    HwpSecurityModuleRegistrationError,
    ProductionHwpResult,
    _default_production_com_factory,
)
from .production_model import ProductionCompanyView, ProductionReportView
from .production_view import build_production_report_view
from .service import build_report_document


OFFICIAL_FILE_PATH_CHECK_DLL = Path(
    r"C:\HancomAutomation\FilePathCheckerModuleExample.dll"
)


class ProductionSecurityModuleMissingError(RuntimeError):
    pass


class ProductionProjectDataError(RuntimeError):
    pass


class ProductionPhotoFileMissingError(RuntimeError):
    pass


def validate_production_document(document) -> None:
    if not document.targets or not any(target.inspection_items for target in document.targets):
        raise ProductionProjectDataError(
            "정식 보고서에 출력할 점검대상과 점검결과가 없습니다"
        )
    missing_photos = [
        warning for warning in document.report_warnings
        if str(warning).startswith("사진 파일 없음:")
    ]
    if missing_photos:
        raise ProductionPhotoFileMissingError("\n".join(missing_photos))


def verify_production_hwp_environment(
    dll_path: str | Path = OFFICIAL_FILE_PATH_CHECK_DLL,
    *,
    com_factory: Callable[[], Any] | None = None,
) -> None:
    dll = Path(dll_path)
    if not dll.is_file():
        raise ProductionSecurityModuleMissingError(str(dll))
    hwp = None
    try:
        hwp = (com_factory or _default_production_com_factory)()
        registered = hwp.RegisterModule(
            "FilePathCheckDLL", "FilePathCheckerModuleExample"
        )
        if registered is not True:
            raise HwpSecurityModuleRegistrationError(
                "한글 자동화 보안모듈 등록에 실패했습니다"
            )
    except (HwpComUnavailableError, HwpSecurityModuleRegistrationError):
        raise
    except Exception as error:
        raise HwpSecurityModuleRegistrationError(
            "한글 자동화 보안모듈 등록 중 오류가 발생했습니다"
        ) from error
    finally:
        if hwp is not None:
            try:
                hwp.Clear(1)
            except Exception:
                pass
            try:
                hwp.Quit()
            except Exception:
                pass


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
    progress_callback: Callable[[str], None] | None = None,
) -> ProductionHwpResult:
    view = prepare_production_report(
        project_data, company_profile_path=company_profile_path
    )
    return (renderer or HwpProductionRenderer()).generate(
        view,
        output_path,
        visible=visible,
        pdf_preview_path=pdf_preview_path,
        progress_callback=progress_callback,
    )
