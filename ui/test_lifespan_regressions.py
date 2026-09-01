import copy
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication, QPushButton
from catalogs.lifespan import DEFAULT_LIFESPAN_SOURCE, LIFESPAN_BY_EQUIPMENT
from main_v316_1_audit_fix import PerformanceInspectionApp
from report.service import build_report_document
from report.production_view import build_production_report_view
from report.hwp_production_renderer import HwpProductionRenderer


class LifespanRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = PerformanceInspectionApp()
        self.saved = {"대상설비": "냉동기", "장비번호계통명": "CH-01",
                      "참고내용연수": "12", "사용연수": "1", "노후도": "정상",
                      "적용근거": "기존 프로젝트 기준"}
        self.window.collect_equipment_register_data = lambda: [
            {"설비종류": "냉동기", "관리번호": "CH-01", "설치연도": "2025"}]

    def tearDown(self):
        self.window.close()

    def row(self):
        return self.window.collect_aging_data()["노후도표"][0]

    def test_default_preset_and_source(self):
        keys = ["냉동기", "팽창탱크", "펌프(냉난방·급수)", "환기설비", "배관설비"]
        self.assertEqual([LIFESPAN_BY_EQUIPMENT[k] for k in keys], [11, 12, 12, 10, 10])
        self.assertEqual(self.window.lifespan_source_combo.currentText(), DEFAULT_LIFESPAN_SOURCE)
        self.assertGreaterEqual(self.window.lifespan_source_combo.findText("한국부동산원 유형고정자산 내용연수표"), 0)

    def test_load_and_passive_refresh_preserve_saved_values(self):
        data = {"노후도표": [self.saved], "내용연수적용근거": "기존 프로젝트 기준"}
        original = copy.deepcopy(data)
        self.window.load_aging_data(data)
        self.window.refresh_aging_table()
        self.window.refresh_system_review_summary()
        for key, value in self.saved.items():
            self.assertEqual(self.row()[key], value)
        self.assertEqual(data, original)

    def test_explicit_button_recalculates_and_labels_actual_preset(self):
        self.window.load_aging_data([self.saved])
        self.window.lifespan_source_combo.setCurrentText("한국부동산원 유형고정자산 내용연수표")
        button = next(b for b in self.window.findChildren(QPushButton)
                      if b.text() == "장비대장에서 노후도 자동계산")
        button.click()
        self.assertEqual(self.row()["참고내용연수"], "11")
        self.assertEqual(self.row()["적용근거"], DEFAULT_LIFESPAN_SOURCE)

    def test_legacy_lifespan_fallback(self):
        for value in [None, "", "   "]:
            with self.subTest(value=value):
                row = dict(self.saved, 참고내용연수=value, 내구연한="12")
                self.window.load_aging_data([row])
                self.assertEqual(self.row()["참고내용연수"], "12")
                view = build_production_report_view(build_report_document({"노후도분석": {"노후도표": [row]}}))
                self.assertEqual(view.aging.rows[0].reference_lifespan, "12")
        row = dict(self.saved)
        row.pop("참고내용연수")
        row["내구연한"] = "12"
        view = build_production_report_view(build_report_document({"노후도분석": [row]}))
        self.assertEqual(view.aging.rows[0].reference_lifespan, "12")

    def test_valid_new_key_takes_precedence(self):
        row = dict(self.saved, 참고내용연수="11", 내구연한="12")
        view = build_production_report_view(build_report_document({"노후도분석": [row]}))
        self.assertEqual(view.aging.rows[0].reference_lifespan, "11")

    def test_legacy_list_and_production_saved_values_are_preserved(self):
        project = {"노후도분석": [self.saved]}
        original = copy.deepcopy(project)
        doc = build_report_document(project)
        view = build_production_report_view(doc)
        self.assertEqual(doc.aging_analysis.rows[0]["참고내용연수"], "12")
        self.assertEqual(view.aging.rows[0].reference_lifespan, "12")
        self.assertEqual(view.aging.rows[0].elapsed_years, "1")
        self.assertEqual(view.aging.rows[0].aging_status, "정상")
        html = HwpProductionRenderer._aging_review(view, 0, 1)
        self.assertIn("<td>12</td><td>1</td><td>정상</td>", html)
        self.assertEqual(project, original)

    def test_unknown_equipment_is_not_zero(self):
        for name in ["미등록 설비", "필터"]:
            with self.subTest(name=name):
                self.window.load_aging_data([])
                self.window.collect_equipment_register_data = lambda: [{"설비종류": name, "관리번호": "U-1"}]
                self.window.refresh_aging_table(recalculate=True)
                self.assertEqual(self.row()["참고내용연수"], "")
                self.assertEqual(self.row()["노후도"], "기준 확인 필요")

    def test_unknown_equipment_preserves_existing_values(self):
        saved = dict(self.saved, 대상설비="미등록 설비")
        self.window.load_aging_data([saved])
        self.window.collect_equipment_register_data = lambda: [{"설비종류": "미등록 설비", "관리번호": "CH-01"}]
        self.window.refresh_aging_table(recalculate=True)
        for key in ["참고내용연수", "사용연수", "노후도", "적용근거"]:
            self.assertEqual(self.row()[key], saved[key])
        self.assertIn("기준 확인 필요", self.row()["비고"])


if __name__ == "__main__":
    unittest.main()
