from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TechnicianPageMixin:

    def create_technician_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("3. 성능점검 기술자")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        notice = QLabel(
            "성능점검에 참여한 기술자의 성명, 등급, 수첩번호와 실제 참여기간을 입력하십시오."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding: 8px; background: #eef6ff; border: 1px solid #8bb8e8;"
        )
        layout.addWidget(notice)

        self.technician_table = QTableWidget()
        self.technician_table.setColumnCount(7)
        self.technician_table.setHorizontalHeaderLabels(
            [
                "구분",
                "성명",
                "등급",
                "수첩번호",
                "참여 시작일",
                "참여 종료일",
                "담당업무",
            ]
        )

        self.technician_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.technician_table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.technician_table.verticalHeader().setVisible(False)
        self.technician_table.setAlternatingRowColors(True)

        header = self.technician_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.Stretch)

        layout.addWidget(self.technician_table)

        button_layout = QHBoxLayout()

        add_button = QPushButton("기술자 추가")
        remove_button = QPushButton("선택 기술자 삭제")
        default_button = QPushButton("직원 5명 불러오기")

        add_button.clicked.connect(self.add_technician_row)
        remove_button.clicked.connect(self.remove_technician_row)
        default_button.clicked.connect(self.add_default_technicians)

        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(default_button)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        bottom_buttons = QHBoxLayout()

        previous_button = QPushButton("이전: 설비현황")
        previous_button.setMinimumHeight(40)
        previous_button.clicked.connect(
            lambda: self.menu.setCurrentRow(1)
        )

        next_button = QPushButton("다음: 점검결과")
        next_button.setMinimumHeight(40)
        next_button.clicked.connect(self.go_to_inspection_page)

        bottom_buttons.addWidget(previous_button)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(next_button)

        layout.addLayout(bottom_buttons)

        return page


    def add_technician_row(self, technician=None):
        row = self.technician_table.rowCount()
        self.technician_table.insertRow(row)

        technician = technician or {}

        role_combo = QComboBox()
        role_combo.addItems(
            [
                "책임기술자",
                "보조기술자",
                "참여기술자",
                "측정담당",
                "사진담당",
            ]
        )
        role_index = role_combo.findText(
            technician.get("구분", "참여기술자")
        )
        if role_index >= 0:
            role_combo.setCurrentIndex(role_index)

        name_combo = QComboBox()
        name_combo.setEditable(True)
        name_combo.addItem("")
        for staff in self._staff_list:
            name_combo.addItem(staff["name"])
        saved_name = technician.get("성명", "")
        name_combo.setCurrentText(saved_name)

        grade_combo = QComboBox()
        grade_combo.addItems(
            ["특급", "고급", "중급", "초급", "기계설비유지관리자", "기타"]
        )
        grade_index = grade_combo.findText(
            technician.get("등급", "초급")
        )
        if grade_index >= 0:
            grade_combo.setCurrentIndex(grade_index)

        start_date = self.create_date_edit()
        end_date = self.create_date_edit()
        self.set_date_value(
            start_date,
            technician.get(
                "참여시작일",
                self.inspection_start.date().toString("yyyy-MM-dd"),
            ),
        )
        self.set_date_value(
            end_date,
            technician.get(
                "참여종료일",
                self.inspection_end.date().toString("yyyy-MM-dd"),
            ),
        )

        license_item = QTableWidgetItem(technician.get("수첩번호", ""))
        duty_item = QTableWidgetItem(
            technician.get("담당업무", "기계설비 성능점검")
        )

        self.technician_table.setCellWidget(row, 0, role_combo)
        self.technician_table.setCellWidget(row, 1, name_combo)
        self.technician_table.setCellWidget(row, 2, grade_combo)
        self.technician_table.setItem(row, 3, license_item)
        self.technician_table.setCellWidget(row, 4, start_date)
        self.technician_table.setCellWidget(row, 5, end_date)
        self.technician_table.setItem(row, 6, duty_item)

        name_combo.currentTextChanged.connect(
            lambda name, r=row: self.apply_staff_info(r, name)
        )

        if saved_name:
            self.apply_staff_info(row, saved_name, preserve_existing=True)

    def apply_staff_info(self, row, name, preserve_existing=False):
        staff = next((item for item in self._staff_list if item["name"] == name), None)
        if not staff:
            return

        grade_widget = self.technician_table.cellWidget(row, 2)
        license_item = self.technician_table.item(row, 3)

        if grade_widget:
            grade_index = grade_widget.findText(staff["grade"])
            if grade_index >= 0 and (not preserve_existing or not grade_widget.currentText()):
                grade_widget.setCurrentIndex(grade_index)
            elif grade_index >= 0 and not preserve_existing:
                grade_widget.setCurrentIndex(grade_index)

        if license_item and (not preserve_existing or not license_item.text().strip()):
            license_item.setText(staff["license"])

    def remove_technician_row(self):
        row = self.technician_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "기술자 선택",
                "삭제할 기술자 행을 먼저 선택하십시오.",
            )
            return

        self.technician_table.removeRow(row)

    def add_default_technicians(self):
        if self.technician_table.rowCount() > 0:
            answer = QMessageBox.question(
                self,
                "직원 5명 불러오기",
                "기존 기술자 목록을 지우고 직원 5명을 불러오시겠습니까?",
            )
            if answer != QMessageBox.Yes:
                return

        self.technician_table.setRowCount(0)

        for index, staff in enumerate(self._staff_list):
            self.add_technician_row(
                {
                    "구분": "책임기술자" if index == 0 else "참여기술자",
                    "성명": staff["name"],
                    "등급": staff["grade"],
                    "수첩번호": staff["license"],
                    "참여시작일": self.inspection_start.date().toString("yyyy-MM-dd"),
                    "참여종료일": self.inspection_end.date().toString("yyyy-MM-dd"),
                    "담당업무": "성능점검 총괄 및 결과검토" if index == 0 else "기계설비 성능점검 및 측정",
                }
            )

    def validate_technicians(self):
        if self.technician_table.rowCount() == 0:
            QMessageBox.warning(
                self,
                "성능점검 기술자 확인",
                "성능점검 책임·참여기술자를 한 명 이상 입력하십시오.",
            )
            return False

        responsible_count = 0

        for row in range(self.technician_table.rowCount()):
            role_widget = self.technician_table.cellWidget(row, 0)
            name_widget = self.technician_table.cellWidget(row, 1)
            license_item = self.technician_table.item(row, 3)

            role = role_widget.currentText()
            name = name_widget.currentText().strip() if name_widget else ""
            license_number = (
                license_item.text().strip() if license_item else ""
            )

            if role == "책임기술자":
                responsible_count += 1

            if not name:
                QMessageBox.warning(
                    self,
                    "성능점검 기술자 확인",
                    f"{row + 1}번째 기술자의 성명을 입력하십시오.",
                )
                return False

            if not license_number:
                QMessageBox.warning(
                    self,
                    "성능점검 기술자 확인",
                    f"{name} 기술자의 수첩번호를 입력하십시오.",
                )
                return False

        if responsible_count == 0:
            QMessageBox.warning(
                self,
                "책임기술자 확인",
                "책임기술자를 한 명 이상 지정하십시오.",
            )
            return False

        return True

    def selected_technician_names(self):
        names = []

        for row in range(self.technician_table.rowCount()):
            name_widget = self.technician_table.cellWidget(row, 1)
            if not name_widget:
                continue

            name = name_widget.currentText().strip()
            if name and name not in names:
                names.append(name)

        return names


    def collect_technician_data(self):
        technicians = []

        for row in range(self.technician_table.rowCount()):
            role_widget = self.technician_table.cellWidget(row, 0)
            grade_widget = self.technician_table.cellWidget(row, 2)
            start_widget = self.technician_table.cellWidget(row, 4)
            end_widget = self.technician_table.cellWidget(row, 5)

            name_widget = self.technician_table.cellWidget(row, 1)
            license_item = self.technician_table.item(row, 3)
            duty_item = self.technician_table.item(row, 6)

            technicians.append(
                {
                    "구분": role_widget.currentText(),
                    "성명": name_widget.currentText().strip() if name_widget else "",
                    "등급": grade_widget.currentText(),
                    "수첩번호": (
                        license_item.text().strip()
                        if license_item
                        else ""
                    ),
                    "참여시작일": start_widget.date().toString(
                        "yyyy-MM-dd"
                    ),
                    "참여종료일": end_widget.date().toString(
                        "yyyy-MM-dd"
                    ),
                    "담당업무": (
                        duty_item.text().strip() if duty_item else ""
                    ),
                }
            )

        return technicians


    def load_technician_data(self, technicians):
        self.technician_table.setRowCount(0)

        for technician in technicians:
            self.add_technician_row(technician)
