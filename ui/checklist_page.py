from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ChecklistPageMixin:
    def create_checklist_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("9. 보고서 자체검증")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        notice = QLabel(
            "서울형 매뉴얼의 보고서 적정성 검토 취지를 반영한 내부 품질관리 체크리스트입니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding: 8px; background: #f3f0ff; border: 1px solid #b7a8e8;"
        )
        layout.addWidget(notice)

        self.report_checklist_table = QTableWidget(
            len(self._report_checklist_items),
            4,
        )
        self.report_checklist_table.setHorizontalHeaderLabels(
            ["번호", "검토항목", "검토결과", "보완내용"]
        )
        self.report_checklist_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.report_checklist_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )
        self.report_checklist_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeToContents
        )
        self.report_checklist_table.horizontalHeader().setSectionResizeMode(
            3, QHeaderView.Stretch
        )

        for row, text in enumerate(self._report_checklist_items):
            number_item = QTableWidgetItem(str(row + 1))
            number_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            text_item = QTableWidgetItem(text)
            text_item.setFlags(
                Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            self.report_checklist_table.setItem(row, 0, number_item)
            self.report_checklist_table.setItem(row, 1, text_item)

            combo = QComboBox()
            combo.addItems(["미검토", "이행", "보완필요", "해당없음"])
            self.report_checklist_table.setCellWidget(row, 2, combo)
            self.report_checklist_table.setItem(
                row, 3, QTableWidgetItem("")
            )

        layout.addWidget(self.report_checklist_table)

        self.checklist_summary = QLabel("검토 전")
        self.checklist_summary.setStyleSheet(
            "padding: 8px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        layout.addWidget(self.checklist_summary)

        button_row = QHBoxLayout()
        check_button = QPushButton("체크리스트 집계")
        check_button.clicked.connect(self.update_checklist_summary)
        auto_button = QPushButton("기본 자동검증")
        auto_button.clicked.connect(self.run_basic_quality_check)
        button_row.addWidget(check_button)
        button_row.addWidget(auto_button)
        button_row.addStretch()
        layout.addLayout(button_row)

        buttons = QHBoxLayout()
        prev_button = QPushButton("이전: 에너지 분석")
        prev_button.clicked.connect(lambda: self.menu.setCurrentRow(7))
        next_button = QPushButton("다음: 보고서 생성")
        next_button.clicked.connect(lambda: self.menu.setCurrentRow(9))
        buttons.addWidget(prev_button)
        buttons.addStretch()
        buttons.addWidget(next_button)
        layout.addLayout(buttons)

        return page

    def collect_checklist_data(self):
        rows = []

        for row, text in enumerate(self._report_checklist_items):
            combo = self.report_checklist_table.cellWidget(row, 2)
            note_item = self.report_checklist_table.item(row, 3)
            rows.append(
                {
                    "번호": row + 1,
                    "검토항목": text,
                    "검토결과": combo.currentText(),
                    "보완내용": (
                        note_item.text().strip()
                        if note_item
                        else ""
                    ),
                }
            )

        return rows

    def update_checklist_summary(self):
        counts = {
            "미검토": 0,
            "이행": 0,
            "보완필요": 0,
            "해당없음": 0,
        }

        for row in range(self.report_checklist_table.rowCount()):
            combo = self.report_checklist_table.cellWidget(row, 2)
            counts[combo.currentText()] += 1

        self.checklist_summary.setText(
            f"이행 {counts['이행']}건 | "
            f"보완필요 {counts['보완필요']}건 | "
            f"미검토 {counts['미검토']}건 | "
            f"해당없음 {counts['해당없음']}건"
        )

    def run_basic_quality_check(self):
        results = [
            bool(self.collect_target_selection_data()),
            bool(self.collect_technician_data()),
            bool(self.collect_photo_data()),
            bool(self.collect_system_review_data().get("검토사항총괄")),
            bool(self.collect_aging_data()),
            bool(self.collect_energy_data().get("연도별사용량")),
        ]

        auto_indexes = [2, 3, 7, 9, 10, 11]

        for index, passed in zip(auto_indexes, results):
            combo = self.report_checklist_table.cellWidget(index, 2)
            combo.setCurrentText("이행" if passed else "보완필요")

        self.update_checklist_summary()

    def load_checklist_data(self, rows):
        saved = {
            item.get("번호"): item
            for item in rows
        }

        for row in range(self.report_checklist_table.rowCount()):
            item = saved.get(row + 1, {})
            combo = self.report_checklist_table.cellWidget(row, 2)
            combo.setCurrentText(
                item.get("검토결과", "미검토")
            )
            self.report_checklist_table.item(row, 3).setText(
                item.get("보완내용", "")
            )

        self.update_checklist_summary()
