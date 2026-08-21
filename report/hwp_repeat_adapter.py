"""Anchor-based target sections and variable HWP tables."""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from .hwp_adapter import (
    HwpAdapterError,
    HwpGenerationResult,
    HwpTextAdapter,
    TemplateContractError,
    parse_hwp_field_list,
)
from .model import ReportDocument
from .repeat_service import RepeatRenderPlan, TargetRepeatBlock, build_repeat_render_plan
from .template_contract import TemplateContract, validate_template_contract


def _cell_text(value: Any) -> str:
    """Keep all text while protecting TSV row and column delimiters."""
    return str(value or "").replace("\t", " ").replace("\r", " ").replace("\n", " ")


class HwpComRepeatWriter:
    """Insert contract-planned tables at a named HWP field anchor."""

    def __init__(self, hwp: Any):
        self.hwp = hwp

    def _insert_text(self, text: str) -> None:
        parameters = self.hwp.HParameterSet.HInsertText
        self.hwp.HAction.GetDefault("InsertText", parameters.HSet)
        parameters.Text = text
        if self.hwp.HAction.Execute("InsertText", parameters.HSet) is False:
            raise HwpAdapterError("HWP 텍스트 삽입에 실패했습니다")

    def _insert_table(self, columns: tuple[Any, ...], block: TargetRepeatBlock) -> None:
        rows = [[column.header for column in columns]]
        rows.extend([list(item.values) for item in block.item_rows])
        table_text = "\r\n".join(
            "\t".join(_cell_text(cell) for cell in row) for row in rows
        )
        start = self.hwp.GetPos()
        self._insert_text(table_text)
        end = self.hwp.GetPos()
        if not self.hwp.SelectText(start[1], start[2], end[1], end[2]):
            raise HwpAdapterError("점검항목 표 변환 범위를 선택하지 못했습니다")
        parameters = self.hwp.HParameterSet.HTableStrToTbl
        self.hwp.HAction.GetDefault("TableStringToTable", parameters.HSet)
        parameters.TableCreation.Rows = len(rows)
        parameters.TableCreation.Cols = len(columns)
        if self.hwp.HAction.Execute("TableStringToTable", parameters.HSet) is False:
            raise HwpAdapterError("점검항목 가변 표 생성에 실패했습니다")

    def insert_plan(self, plan: RepeatRenderPlan, page_break_between: bool) -> None:
        # Append at the anchor field end so earlier target tables are never reselected.
        for source_index, block in enumerate(plan.targets):
            if self.hwp.MoveToField(plan.marker_start, True, False, False) is False:
                raise HwpAdapterError(
                    f"반복 섹션 anchor로 이동하지 못했습니다: {plan.marker_start}"
                )
            if page_break_between and source_index > 0:
                if self.hwp.HAction.Run("BreakPage") is False:
                    raise HwpAdapterError("target 페이지 나눔 삽입에 실패했습니다")
            header = (
                f"설비종류: {_cell_text(block.equipment_type)}\r\n"
                f"관리번호: {_cell_text(block.management_no)}\r\n"
                f"설치위치: {_cell_text(block.location)}\r\n"
                f"주요사양: {_cell_text(block.specification)}\r\n"
                f"점검대상: {_cell_text(block.target_label)}\r\n"
            )
            self._insert_text(header)
            self._insert_table(plan.columns, block)


class HwpReportAdapter(HwpTextAdapter):
    """Phase 2 text fields plus Phase 3 target repeat sections."""

    def __init__(
        self,
        com_factory: Callable[[], Any] | None = None,
        writer_factory: Callable[[Any], Any] | None = None,
    ):
        super().__init__(com_factory)
        self._writer_factory = writer_factory or HwpComRepeatWriter

    def generate(
        self,
        document: ReportDocument,
        contract: TemplateContract,
        template_path: str | os.PathLike[str],
        output_path: str | os.PathLike[str],
        visible: bool = False,
    ) -> HwpGenerationResult:
        template = Path(template_path).resolve()
        output = Path(output_path).resolve()
        if not template.is_file():
            raise HwpAdapterError(f"템플릿 파일이 없습니다: {template}")
        if not output.parent.is_dir():
            raise HwpAdapterError(f"출력 폴더가 없습니다: {output.parent}")
        if template == output:
            raise HwpAdapterError("원본 템플릿을 출력 파일로 직접 사용할 수 없습니다")

        handle, temporary_name = tempfile.mkstemp(
            prefix=f".{output.stem}_", suffix=template.suffix, dir=output.parent
        )
        os.close(handle)
        temporary = Path(temporary_name)
        hwp = None
        validation = None
        written = []
        repeat_warnings = []
        try:
            shutil.copy2(template, temporary)
            hwp = self._com_factory()
            self._set_visibility(hwp, visible)
            if hwp.Open(str(temporary)) is False:
                raise HwpAdapterError("임시 템플릿을 열지 못했습니다")
            fields = parse_hwp_field_list(hwp.GetFieldList(0, 0))
            validation = validate_template_contract(
                document, contract, fields, self._template_metadata(hwp, fields)
            )
            if not validation.valid:
                raise TemplateContractError(validation)

            for name, value in validation.values.items():
                hwp.PutFieldText(name, value)
                written.append(name)

            writer = self._writer_factory(hwp)
            for repeat_contract in contract.repeat_sections:
                plan = build_repeat_render_plan(document, repeat_contract)
                repeat_warnings.extend(plan.warnings)
                writer.insert_plan(plan, repeat_contract.page_break_between)

            saved = hwp.SaveAs(str(temporary), "HWP", "")
            if saved is False:
                raise HwpAdapterError("HWP SaveAs가 실패했습니다")
            self._close(hwp)
            self._quit(hwp)
            hwp = None
            if not temporary.is_file() or temporary.stat().st_size <= 0:
                raise HwpAdapterError("저장된 임시 HWP 파일이 없거나 비어 있습니다")
            os.replace(temporary, output)
            if not output.is_file() or output.stat().st_size <= 0:
                raise HwpAdapterError("최종 HWP 파일이 없거나 비어 있습니다")
            return HwpGenerationResult(
                output_path=str(output),
                written_fields=tuple(written),
                warnings=list(validation.warnings) + repeat_warnings,
                information=list(validation.information),
            )
        except (HwpAdapterError, OSError):
            raise
        except Exception as error:
            raise HwpAdapterError(f"HWP 반복 섹션 생성 실패: {error}") from error
        finally:
            if hwp is not None:
                self._close(hwp)
                self._quit(hwp)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
