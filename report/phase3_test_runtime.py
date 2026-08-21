"""Temporary Phase 1-3 runtime helpers for in-application verification."""

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from .hwp_adapter import HwpAdapterError
from .template_contract import (
    MINIMAL_REPEAT_HWP_CONTRACT,
    TEMPLATE_ID_FIELD,
    TEMPLATE_VERSION_FIELD,
)


PHASE3_TEST_TEMPLATE_NAME = "phase3_repeat_test_template.hwp"


def build_current_project_snapshot(app: Any) -> dict[str, Any]:
    """Collect a detached report input without saving or mutating project JSON."""
    return deepcopy({
        "프로그램버전": "phase3-runtime-test",
        "현장정보": app.collect_site_data(),
        "설비현황": app.collect_equipment_data(),
        "참여기술자": app.collect_technician_data(),
        "장비대장": app.collect_equipment_register_data(),
        "점검대상선정": app.collect_target_selection_data(),
        "설비별점검결과": app.inspection_results,
        "원인분석": app.collect_cause_analysis_data(),
        "전년도비교": {
            "전년도프로젝트경로": getattr(app, "previous_project_path", ""),
            "비교결과": getattr(app, "previous_compare_results", []),
        },
        "성능계산": getattr(app, "performance_calculations", []),
        "사진관리": app.collect_photo_data(),
        "시스템검토": app.collect_system_review_data(),
        "노후도분석": app.collect_aging_data(),
        "성능개선계획": app.collect_improvement_data(),
        "에너지분석": app.collect_energy_data(),
        "보고서자체검증": app.collect_checklist_data(),
    })


def _insert_text(hwp: Any, value: str) -> None:
    parameters = hwp.HParameterSet.HInsertText
    hwp.HAction.GetDefault("InsertText", parameters.HSet)
    parameters.Text = value
    if hwp.HAction.Execute("InsertText", parameters.HSet) is False:
        raise HwpAdapterError("테스트 HWP 텍스트 입력에 실패했습니다.")


def _create_field(hwp: Any, name: str, initial_value: str = "") -> None:
    try:
        created = hwp.CreateField(Direction=name, memo=name, name=name)
    except TypeError:
        created = hwp.CreateField(name, name, name)
    if created is False:
        raise HwpAdapterError(f"테스트 HWP 필드를 만들지 못했습니다: {name}")
    if initial_value:
        hwp.PutFieldText(name, initial_value)
    # CreateField leaves the caret inside the new field. Move out before the
    # next label/field is inserted so contract metadata cannot become nested.
    try:
        hwp.MoveToField(name, False, False, False)
        hwp.HAction.Run("MoveRight")
    except Exception as error:
        raise HwpAdapterError(
            f"테스트 HWP 필드 경계를 벗어나지 못했습니다: {name}"
        ) from error


def create_minimal_repeat_template(
    template_path: str | Path,
    com_factory: Any | None = None,
) -> Path:
    """Create a tiny disposable contract template; never touches legacy templates."""
    path = Path(template_path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    hwp = None
    try:
        if com_factory is None:
            import win32com.client

            com_factory = lambda: win32com.client.Dispatch("HWPFrame.HwpObject")
        hwp = com_factory()
        try:
            hwp.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        hwp.HAction.Run("FileNew")
        _insert_text(hwp, "기계설비 성능점검 Phase 1~3 테스트 보고서\r\n\r\n")
        for label, field_name in (
            ("현장명", "SITE_NAME"),
            ("주소", "SITE_ADDRESS"),
            ("관리주체", "MANAGEMENT_ENTITY"),
            ("점검기간", "INSPECTION_PERIOD"),
            ("보고서 작성일", "REPORT_DATE"),
            ("용도", "SITE_USE"),
        ):
            _insert_text(hwp, f"{label}: ")
            _create_field(hwp, field_name)
            _insert_text(hwp, "\r\n")
        _insert_text(hwp, "템플릿 ID: ")
        _create_field(
            hwp, TEMPLATE_ID_FIELD, MINIMAL_REPEAT_HWP_CONTRACT.template_id
        )
        _insert_text(hwp, "\r\n템플릿 버전: ")
        _create_field(
            hwp,
            TEMPLATE_VERSION_FIELD,
            MINIMAL_REPEAT_HWP_CONTRACT.template_version,
        )
        _insert_text(hwp, "\r\n")
        hwp.HAction.Run("BreakPage")
        _create_field(hwp, "TARGETS_REPEAT_ANCHOR")
        saved = hwp.SaveAs(str(path), "HWP", "")
        if saved is False or not path.is_file() or path.stat().st_size <= 0:
            raise HwpAdapterError("Phase 3 최소 테스트 템플릿 저장에 실패했습니다.")
        return path
    except HwpAdapterError:
        raise
    except Exception as error:
        raise HwpAdapterError(f"Phase 3 최소 테스트 템플릿 생성 실패: {error}") from error
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


def phase3_output_path(output_directory: str | Path, site_name: str) -> Path:
    safe = "".join(
        character if character not in '\\/:*?\"<>|' else "_"
        for character in (site_name.strip() or "현장")
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(output_directory).resolve() / f"{safe}_Phase1-3_테스트_{stamp}.hwp"
