import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from main_v316_1_audit_fix import (
    PerformanceInspectionApp,
    production_report_error_message,
)
from report import (
    HwpComUnavailableError,
    HwpSecurityModuleRegistrationError,
    ProductionHwpSaveError,
    ProductionPdfSaveError,
    ProductionPhotoFileMissingError,
    ProductionProjectDataError,
    ProductionSecurityModuleMissingError,
)


class ReportPageHost:
    create_report_page = PerformanceInspectionApp.create_report_page

    def generate_production_report(self):
        pass

    def generate_phase3_test_report(self):
        pass

    def open_phase3_test_report(self):
        pass


class ProductionReportGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_production_and_legacy_buttons_are_both_visible(self):
        host = ReportPageHost()
        page = host.create_report_page()
        page.show()
        self.app.processEvents()
        self.assertEqual(
            host.production_report_button.text(), "정식 결과보고서 생성"
        )
        self.assertTrue(host.production_report_button.isVisible())
        self.assertEqual(
            host.phase3_test_report_button.text(),
            "Phase 1~3 테스트 보고서 생성",
        )
        self.assertTrue(host.phase3_test_report_button.isVisible())

    def test_default_filename_removes_windows_forbidden_characters(self):
        value = PerformanceInspectionApp.safe_filename(
            '현장<>:"/\\|?*_기계설비성능점검_결과보고서.hwp'
        )
        self.assertFalse(any(character in value for character in '<>:"/\\|?*'))
        self.assertTrue(value.endswith("_기계설비성능점검_결과보고서.hwp"))

    def test_production_errors_have_user_safe_messages(self):
        cases = (
            (ProductionSecurityModuleMissingError(r"C:\HancomAutomation\FilePathCheckerModuleExample.dll"), "설치되지 않았습니다"),
            (HwpSecurityModuleRegistrationError("detail"), "등록하지 못했습니다"),
            (HwpComUnavailableError("detail"), "연결하지 못했습니다"),
            (ProductionProjectDataError("detail"), "데이터가 부족합니다"),
            (ProductionPhotoFileMissingError("detail"), "사진 파일을 찾을 수 없습니다"),
            (ProductionHwpSaveError("detail"), "HWP 저장에 실패했습니다"),
            (ProductionPdfSaveError("detail"), "PDF 비교본 변환에 실패했습니다"),
        )
        for error, expected in cases:
            with self.subTest(error=type(error).__name__):
                message = production_report_error_message(error)
                self.assertIn(expected, message)
                self.assertNotIn("Traceback", message)


if __name__ == "__main__":
    unittest.main()
