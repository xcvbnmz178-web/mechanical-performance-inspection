import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox

from main_v316_1_audit_fix import PerformanceInspectionApp


class EnergyReviewIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])
        cls.energy_data = {"에너지사용량": [
            {"연도": "2024", "종류": "가스", "단위": "N㎥", "총 사용량": "100"},
            {"연도": "2024", "종류": "전기", "단위": "kWh", "총 사용량": "200"},
            {"연도": "2025", "종류": "가스", "단위": "N㎥", "총 사용량": "120"},
            {"연도": "2025", "종류": "전기", "단위": "kWh", "총 사용량": "220"},
            {"연도": "2026", "종류": "가스", "단위": "N㎥", "총 사용량": "110"},
            {"연도": "2026", "종류": "전기", "단위": "kWh", "총 사용량": "250"},
        ]}

    def setUp(self):
        self.window = PerformanceInspectionApp()
        self.window.load_energy_data(self.energy_data)
        self.window.calculate_energy_analysis()

    def tearDown(self):
        self.window.close()

    def test_actual_project_energy_review_and_manual_priority(self):
        review = self.window.current_energy_review_data()
        self.assertEqual(review["years"], ["2024", "2025", "2026"])
        self.assertEqual(review["technical_status_label"], "증가원인확인")
        self.window.refresh_system_review_summary()
        energy_item = self.window.system_review_table.item(6, 3)
        self.assertIn("기술검토 상태: 증가원인확인", energy_item.text())
        for year in ("2024년", "2025년", "2026년"):
            self.assertIn(year, energy_item.text())
        self.assertNotIn("X 부적합", energy_item.text())

        energy_item.setText("사용자가 저장한 수동 에너지 검토")
        self.window.refresh_system_review_summary()
        self.assertEqual(energy_item.text(), "사용자가 저장한 수동 에너지 검토")
        self.assertIn("자동계산 제안", energy_item.toolTip())

    def test_actual_project_chart_has_separate_panels_and_png(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.current_file = str(Path(directory) / "project.json")
            self.assertTrue(self.window.create_energy_chart())
            chart = Path(self.window.energy_chart_path)
            self.assertTrue(chart.is_file() and chart.stat().st_size > 0)
            self.assertEqual(chart.name, "_energy_trend_chart.png")

    def test_calculate_updates_live_chart_for_three_year_electricity_and_gas(self):
        with tempfile.TemporaryDirectory() as directory:
            self.window.current_file = str(Path(directory) / "project.json")
            self.window.show()
            self.window.menu.setCurrentRow(7)
            self.qt_app.processEvents()
            values = {
                ("2024", "city_gas"): 100,
                ("2024", "electricity"): 200,
                ("2025", "city_gas"): 120,
                ("2025", "electricity"): 220,
                ("2026", "city_gas"): 110,
                ("2026", "electricity"): 250,
            }
            for row in range(self.window.energy_table.rowCount()):
                year = self.window.energy_table.item(row, 0).text()
                raw_type = self.window.energy_table.item(row, 1).text()
                from energy.service import normalize_energy_type
                energy_type, _definition = normalize_energy_type(raw_type)
                self.window.energy_table.item(row, 3).setText(
                    str(values.get((year, energy_type), ""))
                )
            self.window.calculate_energy_analysis()
            self.qt_app.processEvents()

            chart = Path(self.window.energy_chart_path)
            pixmap = self.window.energy_chart_label.pixmap()
            self.assertTrue(chart.is_file())
            self.assertGreater(chart.stat().st_size, 0)
            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())
            self.assertTrue(self.window.energy_chart_label.isVisible())
            self.assertGreater(self.window.energy_chart_label.width(), 0)
            self.assertGreater(self.window.energy_chart_label.height(), 0)
            self.assertEqual(
                self.window.energy_chart_error_detail,
                "",
            )

    def test_saved_source_data_recreates_chart_without_saved_png_dependency(self):
        saved = self.window.collect_energy_data()
        with tempfile.TemporaryDirectory() as directory:
            other = PerformanceInspectionApp()
            try:
                other.current_file = str(Path(directory) / "moved-project.json")
                other.load_energy_data(saved)
                self.qt_app.processEvents()
                chart = Path(other.energy_chart_path)
                self.assertEqual(chart.parent, Path(directory))
                self.assertTrue(chart.is_file() and chart.stat().st_size > 0)
                self.assertIsNotNone(other.energy_chart_label.pixmap())
                self.assertFalse(other.energy_chart_label.pixmap().isNull())
            finally:
                other.close()

    def test_live_chart_handles_sparse_and_single_source_year_sets(self):
        from energy.service import normalize_energy_type

        scenarios = (
            {("2026", "electricity"): 10},
            {("2025", "city_gas"): 20, ("2026", "city_gas"): 21},
            {("2024", "electricity"): 10, ("2026", "electricity"): 12},
            {("2024", "city_gas"): 10, ("2025", "city_gas"): 11, ("2026", "city_gas"): 12},
        )
        with tempfile.TemporaryDirectory() as directory:
            self.window.current_file = str(Path(directory) / "project.json")
            for values in scenarios:
                self.window.energy_table.blockSignals(True)
                try:
                    for row in range(self.window.energy_table.rowCount()):
                        year = self.window.energy_table.item(row, 0).text()
                        raw_type = self.window.energy_table.item(row, 1).text()
                        energy_type, _definition = normalize_energy_type(raw_type)
                        self.window.energy_table.item(row, 3).setText(
                            str(values.get((year, energy_type), ""))
                        )
                finally:
                    self.window.energy_table.blockSignals(False)
                self.window.calculate_energy_analysis()
                pixmap = self.window.energy_chart_label.pixmap()
                self.assertIsNotNone(pixmap)
                self.assertFalse(pixmap.isNull())

    def test_empty_energy_chart_reports_reason_without_crash(self):
        for row in range(self.window.energy_table.rowCount()):
            self.window.energy_table.item(row, 3).setText("")
        with patch.object(QMessageBox, "information") as message:
            self.assertFalse(self.window.create_energy_chart())
            message.assert_called_once()
        self.assertIn("자료가 없어", self.window.energy_chart_label.text())

    def test_dynamic_rows_and_district_heating_chart(self):
        rows = [
            {"연도": "2024", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "100"},
            {"연도": "2025", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "105"},
            {"연도": "2024", "종류": "지역난방 냉방사용량", "단위": "Gcal", "총 사용량": "30"},
            {"연도": "2025", "종류": "지역난방 냉방사용량", "단위": "Gcal", "총 사용량": "31"},
            {"연도": "2024", "종류": "기타 열원", "단위": "MJ", "총 사용량": "5"},
            {"연도": "2025", "종류": "기타 열원", "단위": "MJ", "총 사용량": "6"},
            {"연도": "2026", "종류": "기타 열원", "단위": "MJ", "총 사용량": "7"},
        ]
        self.window.load_energy_data({"에너지사용량": rows})
        self.assertEqual(self.window.energy_table.rowCount(), 7)
        review = self.window.current_energy_review_data()
        self.assertIn("district_heating", review["series_by_type"])
        self.assertIn("district_cooling", review["series_by_type"])
        self.assertIn("district_total", review["series_by_type"])
        with tempfile.TemporaryDirectory() as directory:
            self.window.current_file = str(Path(directory) / "project.json")
            self.assertTrue(self.window.create_energy_chart())
            self.assertGreater(Path(self.window.energy_chart_path).stat().st_size, 0)

    def test_loading_legacy_names_does_not_rewrite_them(self):
        legacy = {"에너지사용량": [
            {"연도": "2025", "종류": "전기", "단위": "kWh", "총 사용량": "10"},
            {"연도": "2025", "종류": "가스", "단위": "N㎥", "총 사용량": "20"},
        ]}
        self.window.load_energy_data(legacy)
        self.assertEqual(self.window.energy_table.item(0, 1).text(), "전기")
        self.assertEqual(self.window.energy_table.item(1, 1).text(), "가스")
        review = self.window.current_energy_review_data()
        self.assertIn("electricity", review["series_by_type"])
        self.assertIn("city_gas", review["series_by_type"])

    def test_toe_recalculates_after_usage_change_and_total_change_is_separate(self):
        self.window.load_energy_data({"에너지사용량": [
            {"연도": "2024", "종류": "전기", "단위": "kWh", "총 사용량": "100", "TOE/년": "999"},
            {"연도": "2025", "종류": "전기", "단위": "kWh", "총 사용량": "110", "TOE/년": "999"},
            {"연도": "2026", "종류": "전기", "단위": "kWh", "총 사용량": "121", "TOE/년": "999"},
        ]})
        expected = 100 * float(self.window.electric_toe_factor.text())
        self.assertAlmostEqual(float(self.window.energy_table.item(0, 4).text()), expected, places=3)
        self.window.energy_table.item(0, 3).setText("200")
        expected_changed = 200 * float(self.window.electric_toe_factor.text())
        self.assertAlmostEqual(float(self.window.energy_table.item(0, 4).text()), expected_changed, places=3)
        self.assertEqual(self.window.primary_energy_table.item(2, 6).text(), "+10.00")
        self.assertNotEqual(
            self.window.energy_table.item(2, 6).text(),
            self.window.primary_energy_table.item(2, 6).text(),
        )

    def test_unconvertible_source_stays_blank_and_layout_prioritizes_input(self):
        self.window.load_energy_data({"에너지사용량": [
            {"연도": "2025", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "10"},
            {"연도": "2026", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "11"},
        ]})
        self.assertEqual(self.window.energy_table.item(0, 4).text(), "")
        self.assertEqual(self.window.energy_table.item(0, 5).text(), "")
        layout = self.window.energy_table.parentWidget().layout()
        self.assertLess(layout.indexOf(self.window.energy_table), layout.indexOf(self.window.energy_chart_label))
        self.assertEqual(layout.indexOf(self.window.energy_result_summary), -1)
        self.assertTrue(self.window.energy_result_summary.isHidden())
        self.assertLessEqual(self.window.energy_chart_label.maximumHeight(), 240)

    def test_legacy_result_summary_is_loaded_but_hidden_and_not_recalculated(self):
        data = {
            "에너지사용량": [
                {"연도": "2026", "종류": "전기", "단위": "kWh", "총 사용량": "10"}
            ],
            "결과요약": "기존 프로젝트 저장 요약",
        }
        self.window.load_energy_data(data)
        self.assertTrue(self.window.energy_result_summary.isHidden())
        self.assertEqual(
            self.window.energy_result_summary.toPlainText(),
            "기존 프로젝트 저장 요약",
        )
        self.window.calculate_energy_analysis()
        self.assertEqual(
            self.window.energy_result_summary.toPlainText(),
            "기존 프로젝트 저장 요약",
        )


if __name__ == "__main__":
    unittest.main()
