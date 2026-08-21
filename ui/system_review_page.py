from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inspection import evaluate_criteria_completion, measurement_metadata_for
from energy import format_energy_review_summary


class SystemReviewPageMixin:
    def create_system_review_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("6. 기계설비 성능점검 시 검토사항")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 6-1 고정 검토사항 + 현장별 결과요약
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        self.system_review_table = QTableWidget(
            len(self._system_review_fixed_rows), 4
        )
        self.system_review_table.setHorizontalHeaderLabels(
            ["점검항목", "세부 검토사항", "고정 검토기준", "결과 요약"]
        )
        self.system_review_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        for row, values in enumerate(self._system_review_fixed_rows):
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if col < 3:
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.system_review_table.setItem(row, col, item)
            result = QTableWidgetItem("")
            self.system_review_table.setItem(row, 3, result)
        self.system_review_table.itemChanged.connect(
            self._system_review_summary_item_changed
        )
        summary_layout.addWidget(self.system_review_table)

        refresh_summary = QPushButton("점검결과·노후도·에너지 자료로 결과요약 갱신")
        refresh_summary.clicked.connect(self.refresh_system_review_summary)
        summary_layout.addWidget(refresh_summary)
        tabs.addTab(summary_tab, "검토사항 총괄")

        # 6-2 유지관리지침서
        docs_tab = QWidget()
        docs_layout = QVBoxLayout(docs_tab)
        self.guideline_table = QTableWidget(len(self._guideline_documents), 4)
        self.guideline_table.setHorizontalHeaderLabels(
            ["구비서류", "보유상태", "책임기술자 소견", "비고"]
        )
        self.guideline_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )
        self.guideline_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeToContents
        )
        self.guideline_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )
        self.guideline_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch
        )
        for row, doc in enumerate(self._guideline_documents):
            item = QTableWidgetItem(doc)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.guideline_table.setItem(row, 0, item)
            combo = QComboBox()
            combo.addItems(["유", "무", "해당없음"])
            self.guideline_table.setCellWidget(row, 1, combo)
            self.guideline_table.setItem(row, 2, QTableWidgetItem(""))
            self.guideline_table.setItem(row, 3, QTableWidgetItem(""))
        docs_layout.addWidget(self.guideline_table)
        tabs.addTab(docs_tab, "유지관리지침서 구비현황")

        # 6-3 작동상태
        operation_tab = QWidget()
        operation_layout = QVBoxLayout(operation_tab)
        op_buttons = QHBoxLayout()
        op_refresh = QPushButton("점검대상 설비 불러오기")
        op_refresh.clicked.connect(self.refresh_system_operation_table)
        op_buttons.addWidget(op_refresh)
        op_buttons.addStretch()
        operation_layout.addLayout(op_buttons)
        self.system_operation_table = QTableWidget(0, 4)
        self.system_operation_table.setHorizontalHeaderLabels(
            ["구분", "대상설비", "점검결과", "비고"]
        )
        self.system_operation_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        operation_layout.addWidget(self.system_operation_table)
        tabs.addTab(operation_tab, "시스템 작동상태")

        # 6-4 설계값과 측정값
        design_tab = QWidget()
        design_layout = QVBoxLayout(design_tab)
        design_buttons = QHBoxLayout()
        design_refresh = QPushButton("점검결과에서 설계·측정값 판정 불러오기")
        design_refresh.clicked.connect(self.refresh_design_measure_table)
        design_buttons.addWidget(design_refresh)
        design_buttons.addStretch()
        design_layout.addLayout(design_buttons)
        self.design_measure_table = QTableWidget(0, 5)
        self.design_measure_table.setHorizontalHeaderLabels(
            ["구분", "대상설비", "점검결과", "비교근거", "비고"]
        )
        self.design_measure_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        design_layout.addWidget(self.design_measure_table)
        tabs.addTab(design_tab, "설계값·측정값 일치 여부")

        buttons = QHBoxLayout()
        prev_button = QPushButton("이전: 사진관리")
        prev_button.clicked.connect(lambda: self.menu.setCurrentRow(4))
        next_button = QPushButton("다음: 노후도·개선계획")
        next_button.clicked.connect(lambda: self.menu.setCurrentRow(6))
        buttons.addWidget(prev_button)
        buttons.addStretch()
        buttons.addWidget(next_button)
        layout.addLayout(buttons)
        return page

    @staticmethod
    def equipment_category(name):
        categories = {
            "냉동기": "열원 및 냉난방설비", "냉각탑": "열원 및 냉난방설비",
            "축열조": "열원 및 냉난방설비", "보일러": "열원 및 냉난방설비",
            "열교환기": "열원 및 냉난방설비", "팽창탱크": "열원 및 냉난방설비",
            "펌프(냉난방·급수)": "열원 및 냉난방설비",
            "신재생에너지(태양열·지열)": "열원 및 냉난방설비",
            "연료전지": "열원 및 냉난방설비", "패키지에어컨": "열원 및 냉난방설비",
            "항온항습기": "열원 및 냉난방설비", "공기조화기": "공기조화설비",
            "팬코일유닛": "공기조화설비", "환기설비": "환기설비",
            "필터": "환기설비", "위생기구설비": "위생기구설비",
            "급수·급탕설비": "급수급탕설비", "고·저수조": "급수급탕설비",
            "오·배수통기 및 우수배수설비": "오·배수통기 및 우수배수설비",
            "오수정화설비": "오수정화 및 물재이용설비",
            "물재이용설비": "오수정화 및 물재이용설비",
            "배관설비": "배관설비", "덕트설비": "덕트설비",
            "보온설비": "보온설비", "자동제어설비": "자동제어설비",
            "방음·방진·내진설비": "방음·방진·내진설비",
        }
        return categories.get(name, "")

    def selected_equipment_names(self):
        names = []
        for row in range(self.equipment_table.rowCount()):
            item = self.equipment_table.item(row, 0)
            if item and item.checkState() == Qt.Checked:
                names.append(self._equipment_list[row]["name"])
        return names

    @staticmethod
    def review_item_matches(item_name, keywords):
        normalized = str(item_name).replace(" ", "").lower()
        return any(
            str(keyword).replace(" ", "").lower() in normalized
            for keyword in keywords
        )

    def system_review_criteria_for_item(self, equipment_name, result):
        items = self._inspection_db.get(equipment_name, [])
        item_no = str(result.get("번호", "") or "")
        item_name = str(
            result.get("점검내용")
            or result.get("점검항목")
            or result.get("항목")
            or ""
        )
        matched = None
        if item_no:
            matched = next(
                (
                    item for item in items
                    if str(item.get("no", "")) == item_no
                ),
                None,
            )
        if matched is None and item_name:
            matches = [
                item for item in items
                if str(item.get("name", "")) == item_name
            ]
            if len(matches) == 1:
                matched = matches[0]
        return (
            measurement_metadata_for(matched).get("criteria", [])
            if matched is not None
            else []
        )

    def summarize_system_review_items(self, equipment_name, relevant):
        if not relevant:
            return "/", "관련 점검·계측항목 없음"

        failed = [
            item for item in relevant
            if self.is_final_fail(item.get("판정"))
        ]
        if failed:
            names = [
                str(
                    item.get("점검내용")
                    or item.get("점검항목")
                    or item.get("항목")
                    or ""
                )
                for item in failed
            ]
            return "X", ", ".join([name for name in names if name][:4])

        totals = {
            "pass_rows": 0,
            "final_not_checked": 0,
            "final_not_applicable": 0,
            "final_unused": 0,
            "criterion_fail": 0,
            "criterion_unavailable": 0,
            "criterion_not_checked": 0,
            "criterion_unset": 0,
            "criterion_unused": 0,
            "criterion_all_not_applicable": 0,
            "other_review": 0,
        }

        for item in relevant:
            final = self.normalize_final_judgment(
                item.get("판정", "")
            )
            criteria = self.system_review_criteria_for_item(
                equipment_name, item
            )
            completion = evaluate_criteria_completion(
                criteria, item.get("criteria_results")
            )

            if final == "미점검":
                totals["final_not_checked"] += 1
                continue
            if final == "미사용":
                totals["final_unused"] += 1
                continue
            if final == "/ 해당없음":
                totals["final_not_applicable"] += 1
                continue
            if final != "○ 합격":
                totals["other_review"] += 1
                continue

            if completion["state"] == "no_criteria":
                totals["pass_rows"] += 1
                continue
            if completion["state"] == "all_not_applicable":
                totals["other_review"] += 1
                continue

            totals["criterion_fail"] += completion["fail"]
            totals["criterion_unavailable"] += completion["unavailable"]
            totals["criterion_not_checked"] += completion["not_checked"]
            totals["criterion_unset"] += completion["unset_judgment"]
            totals["criterion_unused"] += completion["unused"]
            if completion["state"] == "complete":
                totals["pass_rows"] += 1

        if totals["final_not_checked"]:
            return (
                "미점검",
                f"최종판정 미점검 {totals['final_not_checked']}건",
            )

        review_parts = []
        labels = [
            ("criterion_fail", "criterion 부적합"),
            ("criterion_unavailable", "확인불가 criterion"),
            ("criterion_not_checked", "미점검 criterion"),
            ("criterion_unset", "미판정 criterion"),
            ("criterion_unused", "미사용 criterion"),
            ("other_review", "판정 재확인"),
        ]
        for key, label in labels:
            if totals[key]:
                review_parts.append(f"{label} {totals[key]}건")

        if review_parts:
            return "확인필요", " / ".join(review_parts)

        if totals["final_unused"]:
            if totals["final_unused"] == len(relevant):
                return "미사용", f"관련항목 {len(relevant)}건 모두 미사용"
            return (
                "확인필요",
                f"적용 항목과 미사용 항목 혼재: 미사용 {totals['final_unused']}건",
            )

        if totals["pass_rows"]:
            return "○", f"적용 관련항목 {totals['pass_rows']}건 완료·합격"

        if totals["final_not_applicable"] == len(relevant):
            return "/", f"관련항목 {len(relevant)}건 모두 해당없음"

        return "확인필요", "관련 점검결과의 완결성 재확인 필요"

    @staticmethod
    def system_review_result_options():
        return ["○", "X", "/", "미사용", "미점검", "확인필요"]

    def create_system_review_result_combo(self, result, calculated=True):
        combo = QComboBox()
        combo.addItems(self.system_review_result_options())
        combo.setCurrentText(result)
        combo.setProperty("calculated_state", bool(calculated))
        combo.currentTextChanged.connect(
            lambda _text, widget=combo: widget.setProperty(
                "calculated_state", False
            )
        )
        return combo

    def existing_system_review_rows(self, table, note_column):
        rows = {}
        for row in range(table.rowCount()):
            name = self.table_item_text(table, row, 1)
            combo = table.cellWidget(row, 2)
            if not name or combo is None:
                continue
            rows[name] = {
                "result": combo.currentText(),
                "note": self.table_item_text(table, row, note_column),
                "calculated": bool(combo.property("calculated_state")),
            }
        return rows

    def equipment_review_result(self, equipment_name, review_kind):
        """
        작동상태와 설계·측정값 판정을 분리한다.
        관련 점검항목이 없으면 해당없음(/), 관련 항목 중 X가 있으면 X.
        """
        self.save_current_inspection_detail()

        relevant = []
        keywords = (
            self._operation_review_keywords
            if review_kind == "operation"
            else self._design_measure_review_keywords
        )

        for row in range(self.target_table.rowCount()):
            target = self.target_row_data(row)
            if target.get("설비종류") != equipment_name:
                continue

            key = self.target_key_from_row(row)
            for item in self.inspection_results.get(key, []):
                item_name = (
                    item.get("점검내용")
                    or item.get("점검항목")
                    or item.get("항목")
                    or ""
                )
                if self.review_item_matches(item_name, keywords):
                    relevant.append(item)

        return self.summarize_system_review_items(
            equipment_name, relevant
        )

    def refresh_system_operation_table(self):
        names = self.selected_equipment_names()
        existing = self.existing_system_review_rows(
            self.system_operation_table, 3
        )
        self.system_operation_table.setRowCount(0)

        for name in names:
            result, note = self.equipment_review_result(
                name,
                "operation",
            )

            row = self.system_operation_table.rowCount()
            self.system_operation_table.insertRow(row)
            self.system_operation_table.setItem(
                row, 0, QTableWidgetItem(self.equipment_category(name))
            )
            self.system_operation_table.setItem(
                row, 1, QTableWidgetItem(name)
            )

            saved = existing.get(name, {})
            preserve_manual = saved and not saved.get("calculated", False)
            display_result = saved.get("result", result) if preserve_manual else result
            display_note = (
                saved.get("note", "")
                if preserve_manual
                else note
            )
            if preserve_manual:
                display_note = (
                    f"{display_note} | 자동계산 제안: {result} ({note})"
                ).strip(" |")
            combo = self.create_system_review_result_combo(
                display_result,
                calculated=not preserve_manual,
            )
            self.system_operation_table.setCellWidget(row, 2, combo)
            self.system_operation_table.setItem(
                row, 3, QTableWidgetItem(display_note)
            )

        self.status_label.setText(
            f"시스템 작동상태 점검표 {len(names)}종 생성"
        )

    def refresh_design_measure_table(self):
        names = self.selected_equipment_names()
        existing = self.existing_system_review_rows(
            self.design_measure_table, 4
        )
        self.design_measure_table.setRowCount(0)

        for name in names:
            result, note = self.equipment_review_result(
                name,
                "design_measure",
            )

            row = self.design_measure_table.rowCount()
            self.design_measure_table.insertRow(row)
            self.design_measure_table.setItem(
                row, 0, QTableWidgetItem(self.equipment_category(name))
            )
            self.design_measure_table.setItem(
                row, 1, QTableWidgetItem(name)
            )

            saved = existing.get(name, {})
            preserve_manual = saved and not saved.get("calculated", False)
            display_result = saved.get("result", result) if preserve_manual else result
            display_note = (
                saved.get("note", "")
                if preserve_manual
                else note
            )
            if preserve_manual:
                display_note = (
                    f"{display_note} | 자동계산 제안: {result} ({note})"
                ).strip(" |")
            combo = self.create_system_review_result_combo(
                display_result,
                calculated=not preserve_manual,
            )
            self.design_measure_table.setCellWidget(row, 2, combo)

            self.design_measure_table.setItem(
                row,
                3,
                QTableWidgetItem(
                    "설계도서·명판·제조사 기준·점검기준과 현장 측정값 비교"
                ),
            )
            self.design_measure_table.setItem(
                row, 4, QTableWidgetItem(display_note)
            )

        self.status_label.setText(
            f"설계값·측정값 일치 여부 {len(names)}종 생성"
        )

    def refresh_defect_improvement_table(self):
        self.save_current_inspection_detail()
        analysis_rows = self.collect_cause_analysis_data()

        analysis_map = {}
        for item in analysis_rows:
            analysis_map[
                (
                    item.get("장비키", ""),
                    str(item.get("점검번호", "")),
                )
            ] = item

        names = self.selected_equipment_names()
        self.defect_improvement_table.setRowCount(0)

        for name in names:
            defects = []
            actions = []

            for row in range(self.target_table.rowCount()):
                target = self.target_row_data(row)
                if target.get("설비종류") != name:
                    continue

                key = self.target_key_from_row(row)

                for item in self.inspection_results.get(key, []):
                    if not self.is_final_fail(item.get("판정")):
                        continue

                    defects.append(
                        item.get("점검내용", "")
                    )

                    analysis = analysis_map.get(
                        (
                            key,
                            str(item.get("번호", "")),
                        )
                    )

                    if analysis:
                        final_cause = analysis.get(
                            "최종원인",
                            "",
                        ).strip()
                        improvement = analysis.get(
                            "개선방안",
                            "",
                        ).strip()

                        if final_cause and improvement:
                            actions.append(
                                f"{final_cause} → {improvement}"
                            )
                        elif improvement:
                            actions.append(
                                improvement
                            )
                    elif item.get("개선방안"):
                        actions.append(
                            item.get("개선방안")
                        )
                    elif item.get("조치사항"):
                        actions.append(
                            item.get("조치사항")
                        )
                    else:
                        special_rule, is_special = self.cause_rule_for_inspection(
                            name,
                            item,
                        )
                        if is_special:
                            actions.append(
                                special_rule.get(
                                    "개선",
                                    "원인 확인 후 개선조치",
                                )
                            )

            row = self.defect_improvement_table.rowCount()
            self.defect_improvement_table.insertRow(row)
            self.defect_improvement_table.setItem(
                row, 0, QTableWidgetItem(self.equipment_category(name))
            )
            self.defect_improvement_table.setItem(
                row, 1, QTableWidgetItem(name)
            )
            self.defect_improvement_table.setItem(
                row, 2, QTableWidgetItem(
                    ", ".join(defects)
                    if defects else "-"
                )
            )
            self.defect_improvement_table.setItem(
                row, 3, QTableWidgetItem(
                    " / ".join(actions)
                    if actions else "-"
                )
            )

    def refresh_system_review_summary(self):
        self.refresh_system_operation_table()
        self.refresh_design_measure_table()
        self.refresh_aging_table()
        self.refresh_defect_improvement_table()
        self.refresh_five_year_plan()
        self.calculate_energy_analysis()

        docs_missing = 0
        for row in range(self.guideline_table.rowCount()):
            combo = self.guideline_table.cellWidget(row, 1)
            if combo.currentText() == "무":
                docs_missing += 1

        operation_bad = 0
        operation_review = 0
        operation_not_applicable = 0
        for row in range(self.system_operation_table.rowCount()):
            combo = self.system_operation_table.cellWidget(row, 2)
            if combo and combo.currentText() == "X":
                operation_bad += 1
            elif combo and combo.currentText() == "/":
                operation_not_applicable += 1
            elif combo and combo.currentText() in {
                "확인필요", "미점검", "미사용"
            }:
                operation_review += 1

        design_bad = 0
        design_review = 0
        design_not_applicable = 0
        for row in range(self.design_measure_table.rowCount()):
            combo = self.design_measure_table.cellWidget(row, 2)
            if combo and combo.currentText() == "X":
                design_bad += 1
            elif combo and combo.currentText() == "/":
                design_not_applicable += 1
            elif combo and combo.currentText() in {
                "확인필요", "미점검", "미사용"
            }:
                design_review += 1

        aging_bad = sum(
            1 for row in range(self.aging_table.rowCount())
            if self.aging_table.item(row, 6)
            and self.aging_table.item(row, 6).text() in {"주의", "교체검토", "교체검토(성능확인 필요)"}
        )

        defect_bad = sum(
            1 for row in range(self.defect_improvement_table.rowCount())
            if self.defect_improvement_table.item(row, 2)
            and self.defect_improvement_table.item(row, 2).text() != "-"
        )

        energy_summary, energy_operation = self.energy_review_proposal_texts()

        summaries = [
            "유지관리지침서 구비상태 양호함" if docs_missing == 0
            else f"미보유 서류 {docs_missing}건으로 보완 필요함",
            (
                f"작동상태 조치필요 설비 {operation_bad}종 확인됨"
                if operation_bad
                else (
                    f"작동상태 확인필요 설비 {operation_review}종 확인됨"
                    if operation_review
                    else (
                        "관련 작동상태 항목 해당없음"
                        if self.system_operation_table.rowCount() > 0
                        and operation_not_applicable
                        == self.system_operation_table.rowCount()
                        else "전 계통 정상 작동함"
                    )
                )
            ),
            (
                f"설계값·측정값 불일치 또는 조치필요 설비 {design_bad}종 확인됨"
                if design_bad
                else (
                    f"설계값·측정값 확인필요 설비 {design_review}종 확인됨"
                    if design_review
                    else (
                        "관련 설계값·측정값 항목 해당없음"
                        if self.design_measure_table.rowCount() > 0
                        and design_not_applicable
                        == self.design_measure_table.rowCount()
                        else "설계값 대비 측정값 허용범위 내 수준으로 양호함"
                    )
                )
            ),
            "내용연수와 성능상태를 종합한 결과 즉시 교체가 필요한 중대결함 없음"
            if aging_bad == 0 else f"노후도 주의·교체검토 설비 {aging_bad}종 확인됨",
            "법적·기술적 기준에 따른 부적합 사항 없음"
            if defect_bad == 0 else f"부적합 및 개선필요 설비 {defect_bad}종 확인됨",
            "노후도와 점검결과에 따른 5개년 단계적 보수·교체계획을 수립함",
            energy_summary,
            energy_operation,
        ]
        for row, summary in enumerate(summaries):
            if row in {6, 7}:
                self._apply_energy_review_proposal(row, summary)
            else:
                self.system_review_table.item(row, 3).setText(summary)

    def energy_review_proposal_texts(self):
        energy_review = self.current_energy_review_data()
        energy_summary = format_energy_review_summary(energy_review)
        energy_operation = self.energy_operation_opinion.toPlainText().strip()
        if not energy_operation:
            energy_operation = "에너지분석 운용개선의견이 입력되지 않았습니다."
        return energy_summary, (
            f"기술검토 상태: {energy_review['technical_status_label']}\n"
            f"{energy_operation}"
        )

    def refresh_energy_review_proposals(self):
        """Refresh only energy proposals without recursively recalculating."""
        if not hasattr(self, "system_review_table"):
            return
        energy_summary, energy_operation = self.energy_review_proposal_texts()
        self._apply_energy_review_proposal(6, energy_summary)
        self._apply_energy_review_proposal(7, energy_operation)

    def _system_review_summary_item_changed(self, item):
        if item.column() == 3:
            self.system_review_table.blockSignals(True)
            try:
                item.setData(Qt.UserRole + 20, False)
            finally:
                self.system_review_table.blockSignals(False)

    def _apply_energy_review_proposal(self, row, proposal):
        """Preserve saved/manual text and expose current energy proposal safely."""
        item = self.system_review_table.item(row, 3)
        if item is None:
            item = QTableWidgetItem("")
            self.system_review_table.setItem(row, 3, item)
        current = item.text().strip()
        auto_controlled = bool(item.data(Qt.UserRole + 20))
        self.system_review_table.blockSignals(True)
        try:
            if not current or auto_controlled:
                item.setText(proposal)
                item.setData(Qt.UserRole + 20, True)
                item.setData(Qt.UserRole + 21, proposal)
                item.setToolTip("에너지분석 원본 데이터에서 자동 계산된 기술검토 내용")
            else:
                item.setData(Qt.UserRole + 20, False)
                item.setData(Qt.UserRole + 21, proposal)
                item.setToolTip(
                    "사용자 수동 검토값을 유지했습니다.\n\n자동계산 제안:\n" + proposal
                )
        finally:
            self.system_review_table.blockSignals(False)

    def collect_system_review_data(self):
        summary_rows = []
        for row in range(self.system_review_table.rowCount()):
            def text_at(col):
                item = self.system_review_table.item(row, col)
                return item.text().strip() if item else ""

            summary_rows.append(
                {
                    "점검항목": text_at(0),
                    "세부검토사항": text_at(1),
                    "고정검토기준": text_at(2),
                    "결과요약": text_at(3),
                }
            )

        docs = []
        for row in range(self.guideline_table.rowCount()):
            status_widget = self.guideline_table.cellWidget(row, 1)

            def doc_text(col):
                item = self.guideline_table.item(row, col)
                return item.text().strip() if item else ""

            docs.append(
                {
                    "구비서류": doc_text(0),
                    "보유상태": (
                        status_widget.currentText()
                        if status_widget
                        else "미검토"
                    ),
                    "책임기술자소견": doc_text(2),
                    "비고": doc_text(3),
                }
            )

        operation_rows = []
        for row in range(self.system_operation_table.rowCount()):
            combo = self.system_operation_table.cellWidget(row, 2)
            operation_rows.append(
                {
                    "구분": self.table_item_text(
                        self.system_operation_table, row, 0
                    ),
                    "대상설비": self.table_item_text(
                        self.system_operation_table, row, 1
                    ),
                    "점검결과": combo.currentText() if combo else "/",
                    "비고": self.table_item_text(
                        self.system_operation_table, row, 3
                    ),
                }
            )

        design_rows = []
        for row in range(self.design_measure_table.rowCount()):
            combo = self.design_measure_table.cellWidget(row, 2)
            design_rows.append(
                {
                    "구분": self.table_item_text(
                        self.design_measure_table, row, 0
                    ),
                    "대상설비": self.table_item_text(
                        self.design_measure_table, row, 1
                    ),
                    "점검결과": combo.currentText() if combo else "/",
                    "비교근거": self.table_item_text(
                        self.design_measure_table, row, 3
                    ),
                    "비고": self.table_item_text(
                        self.design_measure_table, row, 4
                    ),
                }
            )

        return {
            "검토사항총괄": summary_rows,
            "유지관리지침서": docs,
            "시스템작동상태": operation_rows,
            "설계측정값일치": design_rows,
        }

    def load_system_review_data(self, data):
        if not isinstance(data, dict):
            return

        for row, saved in enumerate(data.get("검토사항총괄", [])):
            if row < self.system_review_table.rowCount():
                item = self.system_review_table.item(row, 3)
                if item:
                    item.setText(saved.get("결과요약", ""))

        for row, saved in enumerate(data.get("유지관리지침서", [])):
            if row >= self.guideline_table.rowCount():
                break

            combo = self.guideline_table.cellWidget(row, 1)
            if combo:
                combo.setCurrentText(
                    saved.get("보유상태", "유")
                )

            note_item = self.guideline_table.item(row, 2)
            if note_item:
                note_item.setText(
                    saved.get("책임기술자소견", "")
                )

            remark_item = self.guideline_table.item(row, 3)
            if remark_item:
                remark_item.setText(
                    saved.get("비고", "")
                )

        self.system_operation_table.setRowCount(0)
        for saved in data.get("시스템작동상태", []):
            row = self.system_operation_table.rowCount()
            self.system_operation_table.insertRow(row)
            self.system_operation_table.setItem(
                row, 0, QTableWidgetItem(saved.get("구분", ""))
            )
            self.system_operation_table.setItem(
                row, 1, QTableWidgetItem(saved.get("대상설비", ""))
            )
            combo = self.create_system_review_result_combo(
                saved.get("점검결과", "/"),
                calculated=False,
            )
            self.system_operation_table.setCellWidget(row, 2, combo)
            self.system_operation_table.setItem(
                row, 3, QTableWidgetItem(saved.get("비고", ""))
            )

        self.design_measure_table.setRowCount(0)
        for saved in data.get("설계측정값일치", []):
            row = self.design_measure_table.rowCount()
            self.design_measure_table.insertRow(row)
            self.design_measure_table.setItem(
                row, 0, QTableWidgetItem(saved.get("구분", ""))
            )
            self.design_measure_table.setItem(
                row, 1, QTableWidgetItem(saved.get("대상설비", ""))
            )
            combo = self.create_system_review_result_combo(
                saved.get("점검결과", "/"),
                calculated=False,
            )
            self.design_measure_table.setCellWidget(row, 2, combo)
            self.design_measure_table.setItem(
                row, 3, QTableWidgetItem(saved.get("비교근거", ""))
            )
            self.design_measure_table.setItem(
                row, 4, QTableWidgetItem(saved.get("비고", ""))
            )
