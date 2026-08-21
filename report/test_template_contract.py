import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from report.hwp_adapter import (
    HwpAdapterError,
    HwpComUnavailableError,
    HwpTextAdapter,
    TemplateContractError,
    parse_hwp_field_list,
)
from report.model import ReportDocument, SiteSection
from report.template_contract import (
    MINIMAL_HWP_CONTRACT,
    TEMPLATE_ID_FIELD,
    TEMPLATE_VERSION_FIELD,
    validate_template_contract,
)


def report_document():
    return ReportDocument(
        site=SiteSection(
            {
                "현장명": "테스트 현장",
                "주소": "인천광역시",
                "관리주체": "관리사무소",
                "점검시작일": "2026-08-01",
                "점검종료일": "2026-08-02",
                "보고서작성일": "2026-08-10",
                "용도": "공동주택",
            }
        )
    )


class FakeWindow:
    Visible = False


class FakeWindows:
    def Item(self, _index):
        return FakeWindow()


class FakeHwp:
    def __init__(self, fields, open_result=True, save_result=True):
        self.fields = set(fields)
        self.open_result = open_result
        self.save_result = save_result
        self.values = {}
        self.quit_called = False
        self.clear_called = False
        self.XHwpWindows = FakeWindows()

    def Open(self, _path):
        return self.open_result

    def GetFieldList(self, _option, _type):
        return "\x02".join(sorted(self.fields))

    def GetFieldText(self, name):
        return {
            TEMPLATE_ID_FIELD: MINIMAL_HWP_CONTRACT.template_id,
            TEMPLATE_VERSION_FIELD: MINIMAL_HWP_CONTRACT.template_version,
        }.get(name, "")

    def PutFieldText(self, name, value):
        self.values[name] = value

    def SaveAs(self, _path, _format, _options):
        return self.save_result

    def Clear(self, _option):
        self.clear_called = True

    def Quit(self):
        self.quit_called = True


class TemplateContractTests(unittest.TestCase):
    def setUp(self):
        self.required = {item.field_name for item in MINIMAL_HWP_CONTRACT.required_fields}
        self.optional = {item.field_name for item in MINIMAL_HWP_CONTRACT.optional_fields}

    def test_all_fields_and_extra_field(self):
        result = validate_template_contract(
            report_document(), MINIMAL_HWP_CONTRACT, self.required | self.optional | {"EXTRA"}
        )
        self.assertTrue(result.valid)
        self.assertIn("EXTRA", result.information[0])
        self.assertEqual(result.values["INSPECTION_PERIOD"], "2026-08-01 ~ 2026-08-02")

    def test_missing_required_field_is_error(self):
        fields = self.required - {"SITE_NAME"}
        result = validate_template_contract(report_document(), MINIMAL_HWP_CONTRACT, fields)
        self.assertFalse(result.valid)
        self.assertTrue(any("SITE_NAME" in item for item in result.errors))

    def test_missing_optional_field_is_warning(self):
        result = validate_template_contract(report_document(), MINIMAL_HWP_CONTRACT, self.required)
        self.assertTrue(result.valid)
        self.assertTrue(any("SITE_USE" in item for item in result.warnings))

    def test_missing_required_document_value_is_error(self):
        document = report_document()
        document.site.values["현장명"] = ""
        result = validate_template_contract(document, MINIMAL_HWP_CONTRACT, self.required)
        self.assertFalse(result.valid)
        self.assertTrue(any("SITE_NAME" in item for item in result.errors))

    def test_template_version_mismatch(self):
        result = validate_template_contract(
            report_document(),
            MINIMAL_HWP_CONTRACT,
            self.required,
            {TEMPLATE_ID_FIELD: MINIMAL_HWP_CONTRACT.template_id, TEMPLATE_VERSION_FIELD: "9.9"},
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("버전 불일치" in item for item in result.errors))

    def test_field_list_parser(self):
        self.assertEqual(parse_hwp_field_list("A\x02B{{0}}\r\nC;D"), {"A", "B", "C", "D"})


class HwpAdapterTests(unittest.TestCase):
    def setUp(self):
        self.fields = {
            item.field_name for item in MINIMAL_HWP_CONTRACT.fields
        } | {TEMPLATE_ID_FIELD, TEMPLATE_VERSION_FIELD}

    def test_fake_adapter_writes_text_and_keeps_template(self):
        fake = FakeHwp(self.fields)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "minimal.hwp"
            output = root / "output.hwp"
            template.write_bytes(b"fake-hwp-template")
            original = template.read_bytes()
            result = HwpTextAdapter(lambda: fake).generate(
                report_document(), MINIMAL_HWP_CONTRACT, template, output
            )
            self.assertEqual(template.read_bytes(), original)
            self.assertTrue(output.is_file() and output.stat().st_size > 0)
            self.assertEqual(fake.values["SITE_NAME"], "테스트 현장")
            self.assertEqual(set(result.written_fields), {item.field_name for item in MINIMAL_HWP_CONTRACT.fields})
            self.assertTrue(fake.quit_called)

    def test_missing_template_field_stops_before_write(self):
        fake = FakeHwp(self.fields - {"SITE_ADDRESS"})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "minimal.hwp"
            template.write_bytes(b"template")
            with self.assertRaises(TemplateContractError):
                HwpTextAdapter(lambda: fake).generate(
                    report_document(), MINIMAL_HWP_CONTRACT, template, root / "out.hwp"
                )
            self.assertEqual(fake.values, {})
            self.assertTrue(fake.quit_called)

    def test_output_folder_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "minimal.hwp"
            template.write_bytes(b"template")
            with self.assertRaises(HwpAdapterError):
                HwpTextAdapter(lambda: FakeHwp(self.fields)).generate(
                    report_document(), MINIMAL_HWP_CONTRACT, template, Path(directory) / "missing" / "out.hwp"
                )

    def test_com_failure(self):
        def fail():
            raise HwpComUnavailableError("COM failure")
        with tempfile.TemporaryDirectory() as directory:
            template = Path(directory) / "minimal.hwp"
            template.write_bytes(b"template")
            with self.assertRaises(HwpComUnavailableError):
                HwpTextAdapter(fail).generate(
                    report_document(), MINIMAL_HWP_CONTRACT, template, Path(directory) / "out.hwp"
                )

    def test_locked_output_move_cleans_temporary_file(self):
        fake = FakeHwp(self.fields)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "minimal.hwp"
            template.write_bytes(b"template")
            with patch("report.hwp_adapter.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    HwpTextAdapter(lambda: fake).generate(
                        report_document(), MINIMAL_HWP_CONTRACT, template, root / "out.hwp"
                    )
            self.assertEqual(list(root.glob(".out_*.hwp")), [])
            self.assertTrue(fake.quit_called)


if __name__ == "__main__":
    unittest.main()
