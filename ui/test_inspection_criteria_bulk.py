import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QPlainTextEdit

from main_v316_1_audit_fix import PerformanceInspectionApp
from inspection import derive_final_judgment_from_criteria


class CriteriaBulkUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = PerformanceInspectionApp()
        self.row = 6  # 냉동기 '경보 상태': criteria 7개
        self._open_target("target-a")

    def tearDown(self):
        self.window.close()

    def _open_target(self, key):
        self.window.current_detail_equipment_key = key
        self.window.load_equipment_inspection_detail(key, "냉동기")
        self.window.inspection_detail_table.setCurrentCell(self.row, 0)
        self.window.refresh_criteria_results_panel(self.row)
        self.qt_app.processEvents()

    @staticmethod
    def _select(combo, value):
        index = combo.findData(value)
        if index < 0:
            raise AssertionError(f"combo value not found: {value}")
        combo.setCurrentIndex(index)

    def test_bulk_pass_changes_only_not_checked_unset_and_preserves_details(self):
        editors = self.window._criterion_result_editors
        self.assertEqual(len(editors), 7)

        # Eligible criterion with existing evidence/substitution must retain it.
        editors[0]["original_evidence_note"] = "기존 증빙"
        editors[0]["original_substitution"] = {
            "used": True,
            "method": "document",
            "basis": "기존 근거",
            "source_document": "기존 자료",
            "note": "",
        }

        self._select(editors[1]["status"], "checked")
        self._select(editors[1]["judgment"], "fail")
        self._select(editors[2]["status"], "unavailable")
        self._select(editors[3]["status"], "not_applicable")
        self._select(editors[4]["status"], "unused")
        self._select(editors[5]["status"], "checked")
        self._select(editors[5]["judgment"], "pass")

        final_combo = self.window.inspection_detail_table.cellWidget(self.row, 10)
        final_combo.setCurrentText("X 부적합")
        final_before = final_combo.currentText()
        self._select(self.window.criteria_bulk_method, "document")

        changed = self.window.mark_unset_criteria_pass()
        self.assertEqual(changed, 2)
        for index in (0, 6):
            self.assertEqual(editors[index]["status"].currentData(), "checked")
            self.assertEqual(editors[index]["judgment"].currentData(), "pass")
            self.assertTrue(editors[index]["methods"]["document"].isChecked())
        self.assertEqual(editors[1]["judgment"].currentData(), "fail")
        self.assertEqual(editors[2]["status"].currentData(), "unavailable")
        self.assertEqual(editors[3]["status"].currentData(), "not_applicable")
        self.assertEqual(editors[4]["status"].currentData(), "unused")
        self.assertEqual(editors[0]["original_evidence_note"], "기존 증빙")
        self.assertEqual(
            editors[0]["original_substitution"]["basis"], "기존 근거"
        )
        self.assertEqual(final_combo.currentText(), final_before)

    def test_no_method_is_allowed_and_preflight_data_remains_methodless(self):
        self._select(self.window.criteria_bulk_method, "")
        self.window.mark_unset_criteria_pass()
        self.window.store_current_criteria_results()
        values = self.window._criteria_results_by_row[self.row]
        self.assertTrue(all(value["inspection_status"] == "checked" for value in values))
        self.assertTrue(all(value["criterion_judgment"] == "pass" for value in values))
        self.assertTrue(all(value["performed_methods"] == [] for value in values))
        issues = self.window.criterion_preflight_issues(
            self.window.criteria_for_detail_row(self.row),
            values,
            "미점검",
            True,
        )
        self.assertTrue(
            any(issue["code"] == "checked_without_method" for issue in issues)
        )

    def test_save_restore_and_target_isolation(self):
        self.window.mark_unset_criteria_pass()
        self.window.save_current_inspection_detail()
        saved_a = self.window.inspection_results["target-a"][self.row]["criteria_results"]
        self.assertTrue(all(value["criterion_judgment"] == "pass" for value in saved_a))

        self._open_target("target-b")
        values_b = self.window._criteria_results_by_row[self.row]
        self.assertTrue(all(value["inspection_status"] == "not_checked" for value in values_b))
        self.assertNotIn("target-b", self.window.inspection_results)

        self._open_target("target-a")
        restored = self.window._criteria_results_by_row[self.row]
        self.assertTrue(all(value["criterion_judgment"] == "pass" for value in restored))

    def test_equipment_type_switch_does_not_mix_criteria(self):
        self.window.mark_unset_criteria_pass()
        self.window.save_current_inspection_detail()

        self.window.current_detail_equipment_key = "tower-target"
        self.window.load_equipment_inspection_detail("tower-target", "냉각탑")
        tower_row = next(
            row
            for row in range(self.window.inspection_detail_table.rowCount())
            if self.window.criteria_for_detail_row(row)
        )
        self.window.refresh_criteria_results_panel(tower_row)
        tower_values = self.window._criteria_results_by_row[tower_row]
        self.assertTrue(
            all(value["inspection_status"] == "not_checked" for value in tower_values)
        )

        self._open_target("target-a")
        restored = self.window._criteria_results_by_row[self.row]
        self.assertTrue(all(value["criterion_judgment"] == "pass" for value in restored))

    def test_reset_requires_confirmation_and_keeps_final_judgment(self):
        editors = self.window._criterion_result_editors
        self.window.mark_unset_criteria_pass()
        editors[0]["original_evidence_note"] = "보존될 criterion 메모"
        editors[0]["original_substitution"] = {
            "used": True,
            "method": "document",
            "basis": "삭제될 근거",
            "source_document": "",
            "note": "",
        }
        final_combo = self.window.inspection_detail_table.cellWidget(self.row, 10)
        final_combo.setCurrentText("X 부적합")
        final_before = final_combo.currentText()

        with patch.object(QMessageBox, "question", return_value=QMessageBox.No):
            self.assertFalse(self.window.reset_current_criteria_results())
        self.assertEqual(editors[0]["judgment"].currentData(), "pass")

        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertTrue(self.window.reset_current_criteria_results())
        for editor in editors:
            self.assertEqual(editor["status"].currentData(), "not_checked")
            self.assertEqual(editor["judgment"].currentData(), "unset")
            self.assertTrue(all(not box.isChecked() for box in editor["method_groups"].values()))
        self.assertTrue(editors[0]["original_substitution"]["used"])
        self.assertEqual(
            editors[0]["original_evidence_note"], "보존될 criterion 메모"
        )
        self.assertEqual(final_combo.currentText(), "미점검")

    def test_detail_subtabs_prioritize_item_list_and_criteria_scrolls(self):
        self.window.resize(1500, 950)
        self.window.pages.setCurrentWidget(self.window.inspection_page)
        self.window.inspection_tabs.setCurrentIndex(2)
        self._open_target("target-a")
        self.window.show()
        self.qt_app.processEvents()
        self.assertEqual(self.window.detail_subtabs.count(), 2)
        self.assertEqual(self.window.detail_subtabs.tabText(0), "점검내용·판정")
        self.assertEqual(self.window.detail_subtabs.tabText(1), "점검기준별 수행결과")
        self.assertEqual(self.window.detail_subtabs.currentIndex(), 0)
        self.assertGreaterEqual(self.window.inspection_detail_table.minimumHeight(), 320)
        visible_rows = (
            self.window.inspection_detail_table.viewport().height()
            // self.window.inspection_detail_table.verticalHeader().defaultSectionSize()
        )
        self.assertGreaterEqual(visible_rows, 13)
        self.assertTrue(self.window.criteria_results_scroll.widgetResizable())
        self.assertEqual(
            self.window.criteria_results_scroll.widget(),
            self.window.criteria_results_content,
        )
        self.window.inspection_detail_table.setCurrentCell(self.row, 0)
        self.window.refresh_criteria_results_panel(self.row)
        selected = self.window.inspection_detail_table.currentRow()
        self.window.show_current_criteria_results_tab()
        self.qt_app.processEvents()
        self.assertEqual(self.window.detail_subtabs.currentIndex(), 1)
        self.assertEqual(self.window.inspection_detail_table.currentRow(), selected)

    def test_criterion_summary_updates_without_changing_final_judgment(self):
        final_combo = self.window.inspection_detail_table.cellWidget(self.row, 10)
        self.assertEqual(self.window.inspection_detail_table.item(self.row, 13).text(), "기록없음")
        self.window.mark_unset_criteria_pass()
        self.assertEqual(self.window.inspection_detail_table.item(self.row, 13).text(), "7/7 적합")
        self.assertEqual(final_combo.currentText(), "○ 합격")
        editors = self.window._criterion_result_editors
        self._select(editors[0]["judgment"], "fail")
        self.assertEqual(self.window.inspection_detail_table.item(self.row, 13).text(), "부적합 1")
        self.assertEqual(final_combo.currentText(), "X 불합격")

    def test_method_column_is_hidden_but_source_data_is_preserved(self):
        source_method = self.window._current_detail_inspection_items[0]["method"]
        self.assertTrue(source_method)
        self.assertTrue(self.window.inspection_detail_table.isColumnHidden(2))
        self.assertEqual(
            self.window.inspection_detail_table.item(0, 2).text(),
            source_method,
        )

    def test_all_item_groups_exist_for_chiller_boiler_and_cooling_tower(self):
        for key, equipment_type, expected in (
            ("chiller", "냉동기", 15),
            ("boiler", "보일러", 11),
            ("tower", "냉각탑", 10),
        ):
            self.window.current_detail_equipment_key = key
            self.window.load_equipment_inspection_detail(key, equipment_type)
            self.window.rebuild_criteria_groups(0)
            self.assertEqual(self.window.inspection_detail_table.rowCount(), expected)
            self.assertEqual(len(self.window._criteria_group_buttons), expected)
            for row in range(expected):
                expected_count = len(self.window.criteria_for_detail_row(row))
                self.assertIn(
                    f"기준 {expected_count}",
                    self.window._criteria_group_buttons[row].text(),
                )

    def test_group_selection_and_final_judgment_stay_bidirectionally_linked(self):
        self._open_target("target-a")
        target_row = 11
        self.window.show_current_criteria_results_tab()
        self.window.select_criteria_group(target_row)
        self.assertEqual(self.window.inspection_detail_table.currentRow(), target_row)
        self.assertEqual(self.window._criteria_panel_row, target_row)
        self.window.detail_subtabs.setCurrentIndex(0)
        self.assertEqual(self.window.inspection_detail_table.currentRow(), target_row)

        final_combo = self.window.inspection_detail_table.cellWidget(target_row, 10)
        final_combo.setCurrentIndex(final_combo.count() - 1)
        self.assertIn(
            f"최종 {final_combo.currentText()}",
            self.window._criteria_group_buttons[target_row].text(),
        )

    def test_judgment_change_does_not_replace_existing_technical_opinion(self):
        opinion = self.window.inspection_detail_table.item(self.row, 11)
        opinion.setText("사용자가 작성한 이상 진동 확인 소견")
        final_combo = self.window.inspection_detail_table.cellWidget(self.row, 10)
        final_combo.setCurrentText("X 불합격")
        self.window.refresh_technical_opinion_candidates(self.row)
        self.assertGreaterEqual(
            self.window.technical_opinion_candidate_combo.findData(
                self.window.default_fail_reason()
            ),
            0,
        )
        final_combo.setCurrentText("○ 합격")
        self.assertEqual(opinion.text(), "사용자가 작성한 이상 진동 확인 소견")

    def test_pass_candidate_updates_single_item_opinion_and_main_cell_immediately(self):
        opinion = self.window.inspection_detail_table.item(self.row, 11)
        opinion.setText("기존 사용자 소견")
        expected = self.window.default_pass_reason(self.row)
        final_combo = self.window.inspection_detail_table.cellWidget(self.row, 10)
        final_combo.setCurrentText("○ 합격")
        self.window.refresh_technical_opinion_candidates(self.row)
        index = self.window.technical_opinion_candidate_combo.findData(expected)
        self.assertGreaterEqual(index, 0)
        self.assertEqual(opinion.text(), "기존 사용자 소견")
        self.window.technical_opinion_candidate_combo.setCurrentIndex(index)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
            self.assertTrue(self.window.apply_selected_technical_opinion())
        self.assertEqual(self.window.criteria_item_opinion.toPlainText(), expected)
        self.assertEqual(opinion.text(), expected)

    def test_current_equipment_bulk_pass_updates_only_metadata_criteria(self):
        self.window.store_current_criteria_results()
        before = {
            row: [dict(value) for value in values]
            for row, values in self.window._criteria_results_by_row.items()
        }
        changed = self.window.mark_all_unset_criteria_pass_for_current_equipment()
        self.assertGreater(changed, 0)
        for row in range(self.window.inspection_detail_table.rowCount()):
            criteria = self.window.criteria_for_detail_row(row)
            if not criteria:
                self.assertNotIn(row, self.window._criteria_results_should_save)
                continue
            values = self.window._criteria_results_by_row[row]
            for old, value in zip(before[row], values):
                eligible = (
                    old["inspection_status"] == "not_checked"
                    and old["criterion_judgment"] == "unset"
                )
                if eligible:
                    self.assertEqual(value["inspection_status"], "checked")
                    self.assertEqual(value["criterion_judgment"], "pass")
                else:
                    self.assertEqual(value, old)
            combo = self.window.inspection_detail_table.cellWidget(row, 10)
            self.assertFalse(combo.isEnabled())

    def test_source_of_truth_edit_policy_keeps_legacy_rows_editable(self):
        combo = self.window.inspection_detail_table.cellWidget(self.row, 10)
        opinion = self.window.inspection_detail_table.item(self.row, 11)
        self.assertTrue(combo.isEnabled())
        self.assertTrue(bool(opinion.flags() & Qt.ItemIsEditable))
        self.window.mark_unset_criteria_pass()
        self.assertFalse(combo.isEnabled())
        self.assertFalse(bool(opinion.flags() & Qt.ItemIsEditable))

    def test_bulk_pass_preserves_user_opinion_and_target_history_is_isolated(self):
        opinion = self.window.inspection_detail_table.item(self.row, 11)
        opinion.setText("target-a 전용 사용자 소견")
        self.window.set_all_items_suitable()
        self.assertEqual(opinion.text(), "target-a 전용 사용자 소견")
        self.window.save_current_inspection_detail()

        self._open_target("target-b")
        candidates = self.window.technical_opinion_candidates(self.row)
        self.assertNotIn(
            "target-a 전용 사용자 소견",
            [candidate["text"] for candidate in candidates],
        )

        self._open_target("target-a")
        self.assertEqual(
            self.window.inspection_detail_table.item(self.row, 11).text(),
            "target-a 전용 사용자 소견",
        )

    def test_criterion_aggregation_rules(self):
        criteria = [{"name": str(index)} for index in range(3)]

        def result(status, judgment="unset", index=0):
            return {
                "criterion_index": index,
                "inspection_status": status,
                "criterion_judgment": judgment,
            }

        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria, [result("checked", "pass", index) for index in range(3)]
            ),
            "○ 합격",
        )
        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria,
                [result("checked", "pass", 0), result("checked", "pass", 1), result("checked", "fail", 2)],
            ),
            "X 불합격",
        )
        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria,
                [result("checked", "pass", 0), result("checked", "pass", 1), result("not_applicable", index=2)],
            ),
            "○ 합격",
        )
        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria, [result("not_applicable", index=index) for index in range(3)]
            ),
            "/ 해당없음",
        )
        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria,
                [result("checked", "pass", 0), result("not_checked", index=1), result("checked", "pass", 2)],
            ),
            "미점검",
        )
        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria,
                [result("checked", "pass", 0), result("unavailable", index=1), result("checked", "pass", 2)],
            ),
            "미점검",
        )
        self.assertEqual(
            derive_final_judgment_from_criteria(
                criteria, [result("unused", index=index) for index in range(3)]
            ),
            "미사용",
        )
        self.assertIsNone(
            derive_final_judgment_from_criteria(
                criteria,
                [result("checked", "pass", 0), result("unused", index=1), result("checked", "pass", 2)],
            )
        )

    def test_three_method_ui_maps_legacy_six_methods_without_rewriting(self):
        editor = self.window._criterion_result_editors[0]
        self.assertEqual(len(editor["method_groups"]), 3)
        self.assertEqual(
            [box.text() for box in editor["method_groups"].values()],
            ["현장 육안확인", "계측 및 작동시험", "서류·성적서 확인"],
        )
        legacy = [
            "visual", "measurement", "operation_test",
            "document", "existing_data", "bms",
        ]
        editor["original_methods"] = legacy
        for box in editor["method_groups"].values():
            box.setChecked(True)
        self.window.store_current_criteria_results()
        self.assertEqual(
            self.window._criteria_results_by_row[self.row][0]["performed_methods"],
            legacy,
        )
        self.assertNotIn("substitution_used", editor)

    def test_item_level_opinion_is_single_and_updates_main_cell_in_real_time(self):
        editors = self.window._criterion_result_editors
        opinion = self.window.inspection_detail_table.item(self.row, 11)
        self.assertTrue(all("evidence_note" not in editor for editor in editors))
        self.assertEqual(
            self.window.criteria_results_panel.findChildren(QPlainTextEdit),
            [self.window.criteria_item_opinion],
        )
        self.window.criteria_item_opinion.setPlainText("항목 전체 점검소견")
        self.qt_app.processEvents()
        self.assertEqual(opinion.text(), "항목 전체 점검소견")
        self.assertEqual(
            self.window.criteria_item_opinion.toPlainText(),
            opinion.text(),
        )

    def test_fail_and_recovery_update_final_judgment_and_rca_immediately(self):
        self.window.mark_unset_criteria_pass()
        editors = self.window._criterion_result_editors
        with patch.object(self.window, "refresh_cause_analysis_table") as refresh:
            self._select(editors[0]["judgment"], "fail")
            self.assertEqual(
                self.window.current_detail_final_judgment(self.row), "X 불합격"
            )
            self.assertTrue(refresh.called)
            refresh.reset_mock()
            self._select(editors[0]["judgment"], "pass")
            self.assertEqual(
                self.window.current_detail_final_judgment(self.row), "○ 합격"
            )
            self.assertTrue(refresh.called)

    def test_legacy_row_without_criteria_results_keeps_saved_final_judgment(self):
        rows = [{} for _ in range(15)]
        rows[self.row] = {"판정": "X 불합격", "기술적소견": "기존 판정 보존"}
        self.window.inspection_results["legacy-target"] = rows
        self._open_target("legacy-target")
        self.assertNotIn(self.row, self.window._criteria_results_should_save)
        self.assertEqual(
            self.window.current_detail_final_judgment(self.row), "X 불합격"
        )
        self.assertEqual(
            self.window.inspection_detail_table.item(self.row, 11).text(),
            "기존 판정 보존",
        )

    def test_legacy_substitution_is_preserved_without_editing_ui(self):
        criteria = self.window.criteria_for_detail_row(self.row)
        values = []
        for index, criterion in enumerate(criteria):
            values.append({
                "criterion_index": index,
                "criterion_name": criterion["name"],
                "inspection_status": "checked",
                "criterion_judgment": "pass",
                "performed_methods": ["existing_data", "bms"],
                "evidence_note": f"과거 criterion 증빙 {index + 1}",
                "substitution": {
                    "used": True,
                    "method": "document",
                    "basis": "과거 대체근거",
                    "source_document": "과거 자료",
                    "note": "과거 메모",
                },
            })
        rows = [{} for _ in range(15)]
        rows[self.row] = {"판정": "○ 합격", "criteria_results": values}
        self.window.inspection_results["legacy-substitution"] = rows
        self._open_target("legacy-substitution")
        editor = self.window._criterion_result_editors[0]
        self.assertNotIn("substitution_used", editor)
        self.assertTrue(editor["original_substitution"]["used"])
        self.assertTrue(editor["method_groups"]["document"].isChecked())
        self.window.store_current_criteria_results()
        self.assertEqual(
            self.window._criteria_results_by_row[self.row][0]["substitution"]["basis"],
            "과거 대체근거",
        )
        self.assertEqual(
            self.window._criteria_results_by_row[self.row][0]["evidence_note"],
            "과거 criterion 증빙 1",
        )

    def test_all_rows_resolve_for_chiller_boiler_and_cooling_tower(self):
        for key, equipment_type, expected in (
            ("all-chiller", "냉동기", 15),
            ("all-boiler", "보일러", 11),
            ("all-tower", "냉각탑", 10),
        ):
            self.window.current_detail_equipment_key = key
            self.window.load_equipment_inspection_detail(key, equipment_type)
            self.window._criteria_panel_row = -1
            self.assertEqual(self.window.inspection_detail_table.rowCount(), expected)
            for row in range(expected):
                criteria = self.window.criteria_for_detail_row(row)
                combo = self.window.inspection_detail_table.cellWidget(row, 10)
                if not criteria:
                    combo.setCurrentText("○ 합격")
                    continue
                values = [
                    {
                        "criterion_index": index,
                        "criterion_name": criterion["name"],
                        "inspection_status": "checked",
                        "criterion_judgment": "pass",
                    }
                    for index, criterion in enumerate(criteria)
                ]
                self.window._criteria_results_by_row[row] = values
                self.window._criteria_results_should_save.add(row)
                self.window.sync_final_judgment_from_criteria(
                    row, criteria, values
                )
                self.assertEqual(
                    combo.currentText(), "○ 합격",
                    f"{equipment_type} row={row} criteria={len(criteria)}",
                )
            self.assertTrue(
                all(
                    self.window.inspection_detail_table.cellWidget(row, 10).currentText()
                    == "○ 합격"
                    for row in range(expected)
                )
            )


if __name__ == "__main__":
    unittest.main()
