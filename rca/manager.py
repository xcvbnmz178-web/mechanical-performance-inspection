from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QTableWidgetItem


class RcaManagerMixin:
    def _visible_cause_analysis_rows(self):
        rows = []
        if not hasattr(self, "cause_analysis_table"):
            return rows
        for row in range(self.cause_analysis_table.rowCount()):
            priority_combo = self.cause_analysis_table.cellWidget(
                row, 8
            )

            rows.append(
                {
                    "장비키": (
                        self.cause_analysis_table.item(row, 0).data(Qt.UserRole)
                        if self.cause_analysis_table.item(row, 0)
                        else ""
                    ),
                    "점검번호": (
                        self.cause_analysis_table.item(row, 1).data(Qt.UserRole)
                        if self.cause_analysis_table.item(row, 1)
                        else ""
                    ),
                    "대상설비": self.table_item_text(
                        self.cause_analysis_table, row, 0
                    ),
                    "점검항목": self.table_item_text(
                        self.cause_analysis_table, row, 1
                    ),
                    "이상현상": self.table_item_text(
                        self.cause_analysis_table, row, 2
                    ),
                    "원인후보": self.table_item_text(
                        self.cause_analysis_table, row, 3
                    ),
                    "원인확인방법": self.table_item_text(
                        self.cause_analysis_table, row, 4
                    ),
                    "최종원인": self.table_item_text(
                        self.cause_analysis_table, row, 5
                    ),
                    "영향": self.table_item_text(
                        self.cause_analysis_table, row, 6
                    ),
                    "개선방안": self.table_item_text(
                        self.cause_analysis_table, row, 7
                    ),
                    "우선순위": (
                        priority_combo.currentText()
                        if priority_combo
                        else "B-단기"
                    ),
                    "기술적소견": self.table_item_text(
                        self.cause_analysis_table, row, 9
                    ),
                }
            )

        return rows

    @staticmethod
    def _cause_analysis_identity(item):
        return (
            str(item.get("장비키", "") or ""),
            str(item.get("점검번호", "") or ""),
        )

    def collect_cause_analysis_data(self):
        """Persist visible X targets while retaining inactive user RCA records."""
        if not hasattr(self, "cause_analysis_table"):
            return list(self.cause_analysis)

        visible = self._visible_cause_analysis_rows()
        merged = {
            self._cause_analysis_identity(item): dict(item)
            for item in getattr(self, "cause_analysis", [])
            if isinstance(item, dict)
        }
        for item in visible:
            merged[self._cause_analysis_identity(item)] = item
        self.cause_analysis = list(merged.values())
        rows = self.cause_analysis
        return rows

    def refresh_cause_analysis_table(self):
        self.save_current_inspection_detail()

        previous = {
            (
                item.get("장비키", ""),
                str(item.get("점검번호", "")),
            ): item
            for item in self.collect_cause_analysis_data()
        }

        candidates = []

        for target_row in range(self.target_table.rowCount()):
            key = self.target_key_from_row(target_row)
            target = self.target_row_data(target_row)
            equipment_name = target.get("설비종류", "")

            for result in self.inspection_results.get(key, []):
                if not self.is_final_fail(result.get("판정")):
                    continue

                candidates.append(
                    (
                        key,
                        target,
                        equipment_name,
                        result,
                    )
                )

        self.cause_analysis_table.setRowCount(0)

        for key, target, equipment_name, result in candidates:
            rule, is_special_rule = self.cause_rule_for_inspection(
                equipment_name,
                result,
            )
            inspection_no = str(result.get("번호", ""))
            old = previous.get(
                (key, inspection_no),
                {},
            )

            # 구버전에서 문서성 항목에 장비 고장원인이 저장된 경우
            # 최종원인을 사용자가 확정하지 않았다면 특수규칙으로 교정
            if is_special_rule and not str(
                old.get("최종원인", "")
            ).strip():
                equipment_rule = self.cause_rule_for_equipment(
                    equipment_name
                )
                old_improvement = str(
                    old.get("개선방안", "")
                ).strip()
                old_candidates = str(
                    old.get("원인후보", "")
                ).strip()

                if (
                    not old
                    or not old_improvement
                    or old_improvement == equipment_rule.get("개선", "")
                    or any(
                        candidate in old_candidates
                        for candidate in equipment_rule.get("원인후보", [])[:2]
                    )
                ):
                    old = {}

            row = self.cause_analysis_table.rowCount()
            self.cause_analysis_table.insertRow(row)

            equipment_label = (
                f"{equipment_name} | "
                f"{target.get('관리번호', '') or '관리번호 미지정'}"
            )

            equipment_item = QTableWidgetItem(
                equipment_label
            )
            equipment_item.setData(
                Qt.UserRole,
                key,
            )
            equipment_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )

            inspection_item = QTableWidgetItem(
                result.get("점검내용", "")
            )
            inspection_item.setData(
                Qt.UserRole,
                inspection_no,
            )
            inspection_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )

            self.cause_analysis_table.setItem(
                row, 0, equipment_item
            )
            self.cause_analysis_table.setItem(
                row, 1, inspection_item
            )

            default_values = [
                old.get("이상현상", rule["증상"]),
                old.get(
                    "원인후보",
                    "\n".join(
                        f"• {value}"
                        for value in rule["원인후보"]
                    ),
                ),
                old.get(
                    "원인확인방법",
                    "\n".join(
                        f"• {value}"
                        for value in rule["확인방법"]
                    ),
                ),
                old.get("최종원인", ""),
                old.get("영향", rule["영향"]),
                old.get("개선방안", rule["개선"]),
            ]

            for col, value in zip(
                range(2, 8),
                default_values,
            ):
                self.cause_analysis_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(value)),
                )

            priority = QComboBox()
            priority.addItems(
                [
                    "A-즉시",
                    "B-단기",
                    "C-중기",
                    "D-관찰관리",
                ]
            )
            priority.setCurrentText(
                old.get(
                    "우선순위",
                    rule.get("우선순위", "B-단기"),
                )
            )
            self.cause_analysis_table.setCellWidget(
                row, 8, priority
            )

            technical_opinion = old.get(
                "기술적소견",
                result.get("기술적소견", ""),
            )
            self.cause_analysis_table.setItem(
                row,
                9,
                QTableWidgetItem(technical_opinion),
            )

        self.cause_analysis = self.collect_cause_analysis_data()
        self.cause_analysis_table.resizeRowsToContents()

        self.status_label.setText(
            f"불합격 항목 {len(candidates)}건의 원인분석표를 생성했습니다."
        )

    def apply_cause_analysis_to_inspection(self):
        # Only currently visible X targets may be applied. Archived RCA records
        # belonging to items that are no longer X remain preserved but inactive.
        analysis_rows = self._visible_cause_analysis_rows()
        applied = 0

        for analysis in analysis_rows:
            key = analysis.get("장비키", "")
            inspection_no = str(
                analysis.get("점검번호", "")
            )
            final_cause = analysis.get(
                "최종원인",
                "",
            ).strip()
            improvement = analysis.get(
                "개선방안",
                "",
            ).strip()
            impact = analysis.get(
                "영향",
                "",
            ).strip()

            if not final_cause:
                continue

            opinion_parts = [
                f"원인분석: {final_cause}",
            ]
            if impact:
                opinion_parts.append(
                    f"영향: {impact}"
                )
            if improvement:
                opinion_parts.append(
                    f"개선방안: {improvement}"
                )

            opinion = " / ".join(opinion_parts)

            for result in self.inspection_results.get(
                key,
                [],
            ):
                if str(result.get("번호", "")) == inspection_no:
                    result["기술적소견"] = opinion
                    result["최종원인"] = final_cause
                    result["영향"] = impact
                    result["개선방안"] = improvement
                    result["우선순위"] = analysis.get(
                        "우선순위",
                        "B-단기",
                    )
                    applied += 1
                    break

        current_key = self.current_detail_equipment_key
        if current_key:
            target = self.find_target_data_by_key(
                current_key
            )
            if target:
                self.load_equipment_inspection_detail(
                    current_key,
                    target["설비종류"],
                )

        self.status_label.setText(
            f"원인분석 결과 {applied}건을 설비별 기술적 소견에 반영했습니다."
        )


    def load_cause_analysis_data(self, rows):
        self.cause_analysis = (
            rows if isinstance(rows, list) else []
        )

        if not hasattr(self, "cause_analysis_table"):
            return

        self.cause_analysis_table.setRowCount(0)

        for saved in self.cause_analysis:
            row = self.cause_analysis_table.rowCount()
            self.cause_analysis_table.insertRow(row)

            equipment_item = QTableWidgetItem(
                saved.get("대상설비", "")
            )
            equipment_item.setData(
                Qt.UserRole,
                saved.get("장비키", ""),
            )
            equipment_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            self.cause_analysis_table.setItem(
                row, 0, equipment_item
            )

            inspection_item = QTableWidgetItem(
                saved.get("점검항목", "")
            )
            inspection_item.setData(
                Qt.UserRole,
                saved.get("점검번호", ""),
            )
            inspection_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            self.cause_analysis_table.setItem(
                row, 1, inspection_item
            )

            mapping = [
                "이상현상",
                "원인후보",
                "원인확인방법",
                "최종원인",
                "영향",
                "개선방안",
            ]
            for col, key in enumerate(
                mapping,
                start=2,
            ):
                self.cause_analysis_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(
                        str(saved.get(key, ""))
                    ),
                )

            priority = QComboBox()
            priority.addItems(
                [
                    "A-즉시",
                    "B-단기",
                    "C-중기",
                    "D-관찰관리",
                ]
            )
            priority.setCurrentText(
                saved.get("우선순위", "B-단기")
            )
            self.cause_analysis_table.setCellWidget(
                row, 8, priority
            )

            self.cause_analysis_table.setItem(
                row,
                9,
                QTableWidgetItem(
                    saved.get("기술적소견", "")
                ),
            )

        self.cause_analysis_table.resizeRowsToContents()

        # Saved rows are an archive; the active table is always derived from
        # current final X judgments. refresh preserves matching user content.
        self.refresh_cause_analysis_table()
