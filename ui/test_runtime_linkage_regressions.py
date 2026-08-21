import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from main_v316_1_audit_fix import PerformanceInspectionApp


class RuntimeLinkageRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = PerformanceInspectionApp()

    def tearDown(self):
        self.window.close()

    def test_rca_active_rows_follow_final_x_and_archive_user_content(self):
        targets = {
            0: {"설비종류": "냉동기", "관리번호": "CH-01"},
            1: {"설비종류": "펌프", "관리번호": "P-01"},
        }
        keys = {0: "target-a", 1: "target-b"}
        self.window.target_table.setRowCount(2)
        self.window.target_key_from_row = lambda row: keys[row]
        self.window.target_row_data = lambda row: targets[row]
        self.window.current_detail_equipment_key = None
        self.window.inspection_results = {
            "target-a": [{"번호": "1", "점검내용": "상태 A", "판정": "X 불합격", "기술적소견": ""}],
            "target-b": [{"번호": "2", "점검내용": "상태 B", "판정": "X 불합격", "기술적소견": ""}],
        }
        self.window.cause_analysis = [{
            "장비키": "target-a", "점검번호": "1", "대상설비": "냉동기 | CH-01",
            "점검항목": "상태 A", "최종원인": "사용자 작성 원인", "개선방안": "보존 조치",
        }]
        self.window.refresh_cause_analysis_table()
        self.assertEqual(self.window.cause_analysis_table.rowCount(), 2)

        self.window.inspection_results["target-a"][0]["판정"] = "○ 합격"
        self.window.refresh_cause_analysis_table()
        self.assertEqual(self.window.cause_analysis_table.rowCount(), 1)
        archived = {
            (row["장비키"], str(row["점검번호"])): row
            for row in self.window.collect_cause_analysis_data()
        }
        self.assertEqual(archived[("target-a", "1")]["최종원인"], "사용자 작성 원인")
        self.assertIn(("target-b", "2"), archived)

        self.window.inspection_results["target-a"][0]["판정"] = "X 불합격"
        self.window.refresh_cause_analysis_table()
        self.assertEqual(self.window.cause_analysis_table.rowCount(), 2)
        target_a_row = next(
            row for row in range(2)
            if self.window.cause_analysis_table.item(row, 0).data(0x0100) == "target-a"
        )
        self.assertEqual(self.window.cause_analysis_table.item(target_a_row, 5).text(), "사용자 작성 원인")

    def test_final_judgment_handler_requests_immediate_rca_refresh(self):
        self.window.current_detail_equipment_key = "target-a"
        self.window.load_equipment_inspection_detail("target-a", "냉동기")
        with patch.object(self.window, "save_current_inspection_detail") as save, patch.object(
            self.window, "refresh_cause_analysis_table"
        ) as refresh:
            self.window.on_final_judgment_changed(0, "X 불합격")
        save.assert_called()
        refresh.assert_called_once()

    def test_actual_saved_performance_record_restores_without_recalculation(self):
        project = {
            "장비대장": [{
                "equipment_id": "test-equipment-id",
                "설비종류": "냉동기",
                "관리번호": "CH-TEST-01",
                "세부유형": "turbo",
            }],
            "성능계산": [{
                "equipment_id": "test-equipment-id",
                "종류": "터보냉동기",
                "장비번호": "CH-TEST-01",
                "관리번호_snapshot": "CH-TEST-01",
                "세부유형_snapshot": "turbo",
                "입력값": {
                    "dFlow": "100", "mFlow": "95",
                    "dIn": "12", "mIn": "12.1",
                    "dOut": "7", "mOut": "7.2",
                    "dCap": "100", "dPow": "90", "mPow": "92",
                },
                "산출결과": [{"항목": "측정 COP", "값": "5.82"}],
                "핵심지표": "COP",
                "핵심값": "5.82",
                "판정": "참고",
                "비고": "테스트 데이터",
            }],
        }
        records = project.get("성능계산", [])
        self.assertEqual(len(records), 1)
        record = records[0]
        self.window.performance_calculations = records
        self.window.load_equipment_register_data(project.get("장비대장", []))
        self.window.refresh_saved_performance_calculations()
        self.assertEqual(self.window.performance_calc_saved_table.rowCount(), 1)

        with patch.object(self.window, "calculate_performance_metric") as calculate:
            self.window.performance_calc_type.setCurrentText(record["종류"])
            index = self.window.performance_calc_equipment.findData(record["equipment_id"])
            self.assertGreaterEqual(index, 0)
            self.window.performance_calc_equipment.setCurrentIndex(index)
            self.qt_app.processEvents()
        calculate.assert_not_called()
        restored = self.window.performance_calc_values()
        for key, value in record["입력값"].items():
            self.assertAlmostEqual(float(restored.get(key, 0)), float(value))
        self.assertEqual(
            self.window.performance_calc_result_table.rowCount(),
            len(record.get("산출결과", [])),
        )
        self.window.save_performance_calculation()
        serialized = json.dumps(
            self.window.performance_calculations, ensure_ascii=False
        )
        reopened = PerformanceInspectionApp()
        try:
            reopened.performance_calculations = json.loads(serialized)
            reopened.load_equipment_register_data(project.get("장비대장", []))
            reopened.refresh_saved_performance_calculations()
            reopened.performance_calc_type.setCurrentText(record["종류"])
            reopened_index = reopened.performance_calc_equipment.findData(
                record["equipment_id"]
            )
            reopened.performance_calc_equipment.setCurrentIndex(reopened_index)
            self.qt_app.processEvents()
            self.assertEqual(reopened.performance_calc_values(), restored)
            self.assertEqual(
                reopened.performance_calc_result_table.rowCount(),
                len(record.get("산출결과", [])),
            )
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
