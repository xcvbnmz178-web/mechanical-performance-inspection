"""Minimal HWP text-field adapter independent from legacy report code."""

import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .model import ReportDocument
from .template_contract import (
    TEMPLATE_ID_FIELD,
    TEMPLATE_VERSION_FIELD,
    ContractValidationResult,
    TemplateContract,
    validate_template_contract,
)


class HwpAdapterError(RuntimeError):
    pass


class HwpComUnavailableError(HwpAdapterError):
    pass


class TemplateContractError(HwpAdapterError):
    def __init__(self, validation: ContractValidationResult):
        self.validation = validation
        super().__init__("; ".join(validation.errors))


@dataclass
class HwpGenerationResult:
    output_path: str
    written_fields: tuple[str, ...] = ()
    warnings: list[str] = field(default_factory=list)
    information: list[str] = field(default_factory=list)


def parse_hwp_field_list(value: Any) -> set[str]:
    """Normalize HWP field-list separators and repeated-field suffixes."""
    text = str(value or "").replace("\r\n", "\x02").replace("\n", "\x02")
    fields = set()
    for item in re.split(r"[\x02;]", text):
        name = re.sub(r"\{\{\d+\}\}$", "", item.strip())
        if name:
            fields.add(name)
    return fields


def _default_com_factory() -> Any:
    try:
        import win32com.client
    except (ImportError, OSError) as error:
        raise HwpComUnavailableError("pywin32 또는 HWP COM을 사용할 수 없습니다") from error
    try:
        return win32com.client.Dispatch("HWPFrame.HwpObject")
    except Exception as error:
        raise HwpComUnavailableError("HWP COM 연결에 실패했습니다") from error


class HwpTextAdapter:
    """Fill non-repeating text fields after validating a TemplateContract."""

    def __init__(self, com_factory: Callable[[], Any] | None = None):
        self._com_factory = com_factory or _default_com_factory

    @staticmethod
    def _set_visibility(hwp: Any, visible: bool) -> None:
        try:
            hwp.XHwpWindows.Item(0).Visible = visible
        except Exception:
            pass

    @staticmethod
    def _close(hwp: Any) -> None:
        try:
            hwp.Clear(1)
        except Exception:
            pass

    @staticmethod
    def _quit(hwp: Any) -> None:
        try:
            hwp.Quit()
        except Exception:
            pass

    @staticmethod
    def _template_metadata(hwp: Any, fields: set[str]) -> dict[str, str]:
        metadata = {}
        for name in (TEMPLATE_ID_FIELD, TEMPLATE_VERSION_FIELD):
            if name not in fields:
                continue
            try:
                metadata[name] = str(hwp.GetFieldText(name) or "").strip()
            except Exception:
                metadata[name] = ""
        return metadata

    def inspect_template(
        self,
        template_path: str | os.PathLike[str],
        visible: bool = False,
    ) -> tuple[set[str], dict[str, str]]:
        path = Path(template_path).resolve()
        if not path.is_file():
            raise HwpAdapterError(f"템플릿 파일이 없습니다: {path}")
        hwp = None
        try:
            hwp = self._com_factory()
            self._set_visibility(hwp, visible)
            if hwp.Open(str(path)) is False:
                raise HwpAdapterError(f"템플릿을 열지 못했습니다: {path}")
            fields = parse_hwp_field_list(hwp.GetFieldList(0, 0))
            return fields, self._template_metadata(hwp, fields)
        except HwpAdapterError:
            raise
        except Exception as error:
            raise HwpAdapterError(f"템플릿 검사 실패: {error}") from error
        finally:
            if hwp is not None:
                self._close(hwp)
                self._quit(hwp)

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
        try:
            shutil.copy2(template, temporary)
            hwp = self._com_factory()
            self._set_visibility(hwp, visible)
            if hwp.Open(str(temporary)) is False:
                raise HwpAdapterError("임시 템플릿을 열지 못했습니다")
            fields = parse_hwp_field_list(hwp.GetFieldList(0, 0))
            metadata = self._template_metadata(hwp, fields)
            validation = validate_template_contract(
                document, contract, fields, metadata
            )
            if not validation.valid:
                raise TemplateContractError(validation)
            for name, value in validation.values.items():
                hwp.PutFieldText(name, value)
                written.append(name)
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
                warnings=list(validation.warnings),
                information=list(validation.information),
            )
        except (HwpAdapterError, OSError):
            raise
        except Exception as error:
            raise HwpAdapterError(f"HWP 텍스트 필드 입력 실패: {error}") from error
        finally:
            if hwp is not None:
                self._close(hwp)
                self._quit(hwp)
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
