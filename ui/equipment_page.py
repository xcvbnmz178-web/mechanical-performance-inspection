import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class EquipmentPageMixin:

    def create_equipment_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("2. 설비현황 및 점검수량")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        notice = QLabel(
            "전체수량을 입력하면 해당 설비가 자동 선택되고 점검수량을 계산합니다. "
            "예비설비와 용량 제외조건은 다음 단계에서 반영합니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding: 8px; background: #fff7d6; border: 1px solid #e6c65c;"
        )
        layout.addWidget(notice)

        survey_box = QTabWidget()
        survey_tab = QWidget()
        survey_layout = QVBoxLayout(survey_tab)

        survey_info = QLabel(
            "대상조사표 원본 파일을 직접 선택하면 표 구조를 읽어 "
            "현장정보와 설비수량을 자동 반영합니다. "
            "복사·붙여넣기는 사용하지 않습니다."
        )
        survey_info.setWordWrap(True)
        survey_layout.addWidget(survey_info)

        self.survey_file_path = QLineEdit()
        self.survey_file_path.setReadOnly(True)
        self.survey_file_path.setPlaceholderText(
            "불러올 대상조사표 파일을 선택하십시오."
        )
        survey_layout.addWidget(self.survey_file_path)

        survey_buttons = QHBoxLayout()
        file_import_button = QPushButton(
            "대상조사표 파일 불러오기"
        )
        file_import_button.setMinimumHeight(42)
        file_import_button.clicked.connect(
            self.import_survey_file
        )
        reload_button = QPushButton(
            "선택 파일 다시 읽기"
        )
        reload_button.clicked.connect(
            self.reload_survey_file
        )
        clear_button = QPushButton(
            "불러온 조사표 해제"
        )
        clear_button.clicked.connect(
            self.clear_survey_file
        )
        survey_buttons.addWidget(file_import_button)
        survey_buttons.addWidget(reload_button)
        survey_buttons.addWidget(clear_button)
        survey_buttons.addStretch()
        survey_layout.addLayout(survey_buttons)

        supported_label = QLabel(
            "지원 형식: HWP, HWPX, XLSX, XLSM, CSV, TXT"
        )
        supported_label.setStyleSheet(
            "color: #4b5563; padding: 2px 0 4px 0;"
        )
        survey_layout.addWidget(supported_label)

        self.survey_result_label = QLabel("불러온 조사표 없음")
        self.survey_result_label.setStyleSheet(
            "padding: 6px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        survey_layout.addWidget(self.survey_result_label)

        survey_box.addTab(survey_tab, "대상조사표 자동입력")
        layout.addWidget(survey_box)

        self.equipment_table = QTableWidget()
        self.equipment_table.setColumnCount(7)
        self.equipment_table.setHorizontalHeaderLabels(
            [
                "선택",
                "기계설비 종류",
                "단위",
                "전체수량",
                "산정대상수량",
                "점검률",
                "점검수량",
            ]
        )

        self.equipment_table.setRowCount(len(self._equipment_list))
        self.equipment_table.verticalHeader().setVisible(False)
        self.equipment_table.setAlternatingRowColors(True)

        header = self.equipment_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        for row, equipment in enumerate(self._equipment_list):
            selected_item = QTableWidgetItem()
            selected_item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsUserCheckable
            )
            selected_item.setCheckState(Qt.Unchecked)
            self.equipment_table.setItem(row, 0, selected_item)

            name_item = QTableWidgetItem(equipment["name"])
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.equipment_table.setItem(row, 1, name_item)

            unit_item = QTableWidgetItem(equipment["unit"])
            unit_item.setTextAlignment(Qt.AlignCenter)
            unit_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.equipment_table.setItem(row, 2, unit_item)

            total_item = QTableWidgetItem("0")
            total_item.setTextAlignment(Qt.AlignCenter)
            self.equipment_table.setItem(row, 3, total_item)

            eligible_item = QTableWidgetItem("0")
            eligible_item.setTextAlignment(Qt.AlignCenter)
            self.equipment_table.setItem(row, 4, eligible_item)

            rate_item = QTableWidgetItem(f'{equipment["rate"]}%')
            rate_item.setTextAlignment(Qt.AlignCenter)
            rate_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.equipment_table.setItem(row, 5, rate_item)

            inspection_item = QTableWidgetItem("0")
            inspection_item.setTextAlignment(Qt.AlignCenter)
            inspection_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.equipment_table.setItem(row, 6, inspection_item)

        self.equipment_table.itemChanged.connect(
            self.on_equipment_item_changed
        )

        layout.addWidget(self.equipment_table)

        summary_layout = QGridLayout()

        self.selected_equipment_count = QLabel("0종")
        self.total_equipment_count = QLabel("0")
        self.total_inspection_count = QLabel("0")

        summary_layout.addWidget(QLabel("선택 설비 종류"), 0, 0)
        summary_layout.addWidget(self.selected_equipment_count, 0, 1)
        summary_layout.addWidget(QLabel("전체 설비 수량"), 0, 2)
        summary_layout.addWidget(self.total_equipment_count, 0, 3)
        summary_layout.addWidget(QLabel("점검 예정 수량"), 0, 4)
        summary_layout.addWidget(self.total_inspection_count, 0, 5)

        layout.addLayout(summary_layout)

        bottom_buttons = QHBoxLayout()

        previous_button = QPushButton("이전: 현장정보")
        previous_button.setMinimumHeight(40)
        previous_button.clicked.connect(self.go_to_site_page)

        next_button = QPushButton("다음: 성능점검 기술자")
        next_button.setMinimumHeight(40)
        next_button.clicked.connect(self.go_to_technician_page)

        bottom_buttons.addWidget(previous_button)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(next_button)

        layout.addLayout(bottom_buttons)

        return page



    def on_equipment_item_changed(self, item):
        row = item.row()
        column = item.column()

        if column not in (0, 3, 4):
            return

        self.equipment_table.blockSignals(True)

        try:
            selected_item = self.equipment_table.item(row, 0)
            total_item = self.equipment_table.item(row, 3)
            eligible_item = self.equipment_table.item(row, 4)
            inspection_item = self.equipment_table.item(row, 6)

            total = self.parse_non_negative_integer(total_item.text())
            eligible = self.parse_non_negative_integer(eligible_item.text())

            total_item.setText(str(total))

            if column == 3:
                eligible = total
                eligible_item.setText(str(total))

                if total > 0:
                    selected_item.setCheckState(Qt.Checked)
                else:
                    selected_item.setCheckState(Qt.Unchecked)

            if eligible > total:
                eligible = total
                eligible_item.setText(str(total))

            rate = self._equipment_list[row]["rate"]
            unit = self._equipment_list[row]["unit"]

            if selected_item.checkState() == Qt.Checked:
                if unit == "식":
                    inspection_count = 1 if total > 0 else 0
                else:
                    inspection_count = (
                        math.ceil(eligible * rate / 100)
                        if eligible > 0
                        else 0
                    )
            else:
                inspection_count = 0

            inspection_item.setText(str(inspection_count))

        finally:
            self.equipment_table.blockSignals(False)

        self.update_equipment_summary()
    @staticmethod
    def parse_non_negative_integer(value):
        try:
            number = int(str(value).strip())
            return max(number, 0)
        except ValueError:
            return 0

    def update_equipment_summary(self):
        selected_count = 0
        total_count = 0
        inspection_count = 0

        for row in range(self.equipment_table.rowCount()):
            selected_item = self.equipment_table.item(row, 0)

            if selected_item.checkState() != Qt.Checked:
                continue

            selected_count += 1
            total_count += self.parse_non_negative_integer(
                self.equipment_table.item(row, 3).text()
            )
            inspection_count += self.parse_non_negative_integer(
                self.equipment_table.item(row, 6).text()
            )

        self.selected_equipment_count.setText(f"{selected_count}종")
        self.total_equipment_count.setText(str(total_count))
        self.total_inspection_count.setText(str(inspection_count))

    def count_selected_equipment(self):
        count = 0

        for row in range(self.equipment_table.rowCount()):
            if self.equipment_table.item(row, 0).checkState() == Qt.Checked:
                count += 1

        return count



    def collect_equipment_data(self):
        equipment_data = []

        for row, equipment in enumerate(self._equipment_list):
            selected = (
                self.equipment_table.item(row, 0).checkState()
                == Qt.Checked
            )

            equipment_data.append(
                {
                    "설비명": equipment["name"],
                    "단위": equipment["unit"],
                    "선택": selected,
                    "전체수량": self.parse_non_negative_integer(
                        self.equipment_table.item(row, 3).text()
                    ),
                    "산정대상수량": self.parse_non_negative_integer(
                        self.equipment_table.item(row, 4).text()
                    ),
                    "점검률": equipment["rate"],
                    "점검수량": self.parse_non_negative_integer(
                        self.equipment_table.item(row, 6).text()
                    ),
                }
            )

        return equipment_data



    def load_equipment_data(self, equipment_data):
        data_by_name = {
            item.get("설비명"): item for item in equipment_data
        }

        self.equipment_table.blockSignals(True)

        try:
            for row, equipment in enumerate(self._equipment_list):
                saved = data_by_name.get(equipment["name"], {})

                self.equipment_table.item(row, 0).setCheckState(
                    Qt.Checked
                    if saved.get("선택", False)
                    else Qt.Unchecked
                )
                self.equipment_table.item(row, 3).setText(
                    str(saved.get("전체수량", 0))
                )
                self.equipment_table.item(row, 4).setText(
                    str(saved.get("산정대상수량", 0))
                )
                self.equipment_table.item(row, 6).setText(
                    str(saved.get("점검수량", 0))
                )

        finally:
            self.equipment_table.blockSignals(False)

        self.update_equipment_summary()
