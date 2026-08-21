from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class SitePageMixin:

    def create_site_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        page_title = QLabel("1. 현장정보")
        page_title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(page_title)

        self.site_info_tabs = QTabWidget()

        # -------------------- 현장정보 1시트 --------------------
        sheet1 = QWidget()
        sheet1_layout = QVBoxLayout(sheet1)
        form1 = QFormLayout()

        self.site_name = QLineEdit()
        self.site_name.setPlaceholderText("예: 테스트센터")

        self.address = QLineEdit()
        self.address.setPlaceholderText("예: 서울특별시 예시구 예시로 00")

        self.building_use = QComboBox()
        self.building_use.addItems(
            [
                "문화 및 집회시설",
                "운동시설",
                "공동주택",
                "업무시설",
                "공장",
                "교육연구시설",
                "판매시설",
                "숙박시설",
                "의료시설",
                "기타",
            ]
        )
        self.building_use.setEditable(True)

        self.inspection_basis = QComboBox()
        self.inspection_basis.addItems(
            [
                "연면적 기준(비주거·공장 등)",
                "세대수 기준(공동주택)",
            ]
        )
        self.inspection_basis.currentIndexChanged.connect(
            self.update_inspection_basis_ui
        )

        self.total_area = QLineEdit()
        self.total_area.setPlaceholderText("예: 43029.12")

        self.households = QSpinBox()
        self.households.setRange(0, 100000)
        self.households.setSpecialValueText("미입력")

        self.ground_floors = QSpinBox()
        self.ground_floors.setRange(0, 200)

        self.basement_floors = QSpinBox()
        self.basement_floors.setRange(0, 50)

        self.completion_date = self.create_date_edit()
        self.reference_date = self.create_date_edit()

        self.management_entity = QLineEdit()
        self.management_entity.setPlaceholderText("예: 테스트관리주체")

        self.management_address = QLineEdit()
        self.management_address.setPlaceholderText(
            "예: 서울특별시 예시구 예시로 00"
        )

        self.representative = QLineEdit()
        self.phone = QLineEdit()

        self.contract_start = self.create_date_edit()
        self.contract_end = self.create_date_edit()
        self.inspection_start = self.create_date_edit()
        self.inspection_end = self.create_date_edit()
        self.report_date = self.create_date_edit()
        self.submit_authority = QLineEdit()
        self.submit_authority.setPlaceholderText(
            "예: 서울특별시 예시구청"
        )
        self.inspection_method = QComboBox()
        self.inspection_method.addItems(
            ["성능점검업체 대행", "관리주체 자체점검"]
        )

        form1.addRow("현장명 *", self.site_name)
        form1.addRow("주소 *", self.address)
        form1.addRow("성능점검 기준 선택 *", self.inspection_basis)
        form1.addRow("건축물 용도", self.building_use)
        form1.addRow("연면적(㎡)", self.total_area)
        form1.addRow("세대수", self.households)
        form1.addRow("지상층수", self.ground_floors)
        form1.addRow("지하층수", self.basement_floors)
        form1.addRow("준공일", self.completion_date)
        form1.addRow("성능점검 기준일", self.reference_date)
        form1.addRow("관리주체 *", self.management_entity)
        form1.addRow("관리주체 주소", self.management_address)
        form1.addRow("대표자·담당자", self.representative)
        form1.addRow("전화번호", self.phone)
        form1.addRow("용역계약 시작일", self.contract_start)
        form1.addRow("용역계약 종료일", self.contract_end)
        form1.addRow("현장점검 시작일", self.inspection_start)
        form1.addRow("현장점검 종료일", self.inspection_end)
        form1.addRow("점검방법", self.inspection_method)
        form1.addRow("보고서 작성일·제출일", self.report_date)
        form1.addRow("제출 관청", self.submit_authority)

        sheet1_layout.addLayout(form1)
        sheet1_layout.addStretch()
        self.site_info_tabs.addTab(sheet1, "현장정보 1")

        # -------------------- 현장정보 2시트 --------------------
        sheet2 = QWidget()
        sheet2_layout = QVBoxLayout(sheet2)
        form2 = QFormLayout()

        self.maintenance_manager = QLineEdit()
        self.maintenance_manager.setPlaceholderText("책임 유지관리자 성명")

        self.maintenance_grade = QComboBox()
        self.maintenance_grade.addItems(
            ["특급", "고급", "중급", "초급", "보조", "해당 없음"]
        )

        self.maintenance_manager2 = QLineEdit()
        self.maintenance_manager2.setPlaceholderText(
            "보조 유지관리자 성명, 없으면 공란"
        )

        self.maintenance_grade2 = QComboBox()
        self.maintenance_grade2.addItems(
            ["특급", "고급", "중급", "초급", "보조", "해당 없음"]
        )

        self.manager1_appointment_date = self.create_date_edit()
        self.manager1_education_date = self.create_date_edit()
        self.manager2_appointment_date = self.create_date_edit()
        self.manager2_education_date = self.create_date_edit()

        self.maintenance_org = QPlainTextEdit()
        self.maintenance_org.setPlaceholderText(
            "선택 입력입니다. 별도 조직도가 없으면 비워두십시오.\n예:\n"
            "책임기계설비유지관리자 | 홍길동 | 기계설비유지관리자 | 책임\n"
            "보조기계설비유지관리자 | 김철수 | 기계설비유지관리자 | 보조\n"
            "안전담당 | 이영희 |  |"
        )
        self.maintenance_org.setMaximumHeight(110)

        form2.addRow("유지관리자 1 성명", self.maintenance_manager)
        form2.addRow("유지관리자 1 등급", self.maintenance_grade)
        form2.addRow("유지관리자 1 선임일", self.manager1_appointment_date)
        form2.addRow("유지관리자 1 교육수료일", self.manager1_education_date)
        form2.addRow("유지관리자 2 성명", self.maintenance_manager2)
        form2.addRow("유지관리자 2 등급", self.maintenance_grade2)
        form2.addRow("유지관리자 2 선임일", self.manager2_appointment_date)
        form2.addRow("유지관리자 2 교육수료일", self.manager2_education_date)
        form2.addRow("기계설비 유지관리 조직도(선택)", self.maintenance_org)

        sheet2_layout.addLayout(form2)

        deferred_notice = QLabel(
            "※ 유지관리지침서 구비현황은 6. 시스템 검토에서 관리합니다. "
            "기존 13페이지 구비현황 및 18페이지 비상연락망은 새 보고서 서식 확정 후 "
            "필요 시 다시 연동할 예정이므로 현재 현장정보 입력에서는 제외했습니다."
        )
        deferred_notice.setWordWrap(True)
        deferred_notice.setStyleSheet(
            "padding: 8px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        sheet2_layout.addWidget(deferred_notice)
        sheet2_layout.addStretch()
        self.site_info_tabs.addTab(sheet2, "현장정보 2")

        layout.addWidget(self.site_info_tabs)

        bottom_buttons = QHBoxLayout()
        bottom_buttons.addStretch()

        next_button = QPushButton("다음: 설비현황")
        next_button.setMinimumHeight(40)
        next_button.clicked.connect(self.go_to_equipment_page)

        bottom_buttons.addWidget(next_button)
        layout.addLayout(bottom_buttons)

        self.update_inspection_basis_ui()

        return page

    def update_inspection_basis_ui(self):
        area_basis = self.inspection_basis.currentIndex() == 0

        self.total_area.setEnabled(area_basis)
        self.households.setEnabled(not area_basis)

        if area_basis:
            self.households.setValue(0)
            self.total_area.setPlaceholderText(
                "필수: 연면적 입력"
            )
        else:
            self.total_area.clear()
            self.total_area.setPlaceholderText(
                "세대수 기준 선택 시 미입력"
            )

    def inspection_basis_key(self):
        return (
            "연면적"
            if self.inspection_basis.currentIndex() == 0
            else "세대수"
        )



    def collect_site_data(self):
        return {
            "현장명": self.site_name.text().strip(),
            "주소": self.address.text().strip(),
            "성능점검기준구분": self.inspection_basis_key(),
            "용도": self.building_use.currentText(),
            "연면적": self.total_area.text().strip(),
            "세대수": self.households.value(),
            "지상층수": self.ground_floors.value(),
            "지하층수": self.basement_floors.value(),
            "준공일": self.completion_date.date().toString("yyyy-MM-dd"),
            "성능점검기준일": self.reference_date.date().toString(
                "yyyy-MM-dd"
            ),
            "관리주체": self.management_entity.text().strip(),
            "관리주체주소": self.management_address.text().strip(),
            "대표자담당자": self.representative.text().strip(),
            "전화번호": self.phone.text().strip(),
            "기계설비유지관리자": self.maintenance_manager.text().strip(),
            "유지관리자등급": self.maintenance_grade.currentText(),
            "기계설비유지관리자2": self.maintenance_manager2.text().strip(),
            "유지관리자등급2": self.maintenance_grade2.currentText(),
            "유지관리자1선임일": self.manager1_appointment_date.date().toString(
                "yyyy-MM-dd"
            ),
            "유지관리자1교육수료일": self.manager1_education_date.date().toString(
                "yyyy-MM-dd"
            ),
            "유지관리자2선임일": self.manager2_appointment_date.date().toString(
                "yyyy-MM-dd"
            ),
            "유지관리자2교육수료일": self.manager2_education_date.date().toString(
                "yyyy-MM-dd"
            ),
            "유지관리조직도": self.maintenance_org.toPlainText().strip(),
            "계약시작일": self.contract_start.date().toString("yyyy-MM-dd"),
            "계약종료일": self.contract_end.date().toString("yyyy-MM-dd"),
            "점검방법": self.inspection_method.currentText(),
            "제출관청": self.submit_authority.text().strip(),
            "점검시작일": self.inspection_start.date().toString(
                "yyyy-MM-dd"
            ),
            "점검종료일": self.inspection_end.date().toString(
                "yyyy-MM-dd"
            ),
            "보고서작성일": self.report_date.date().toString(
                "yyyy-MM-dd"
            ),
        }



    def validate_site_data(self, data):
        required_fields = ["현장명", "주소", "관리주체"]

        missing = [
            field
            for field in required_fields
            if not str(data.get(field, "")).strip()
        ]

        if missing:
            QMessageBox.warning(
                self,
                "현장정보 확인",
                "다음 필수항목을 입력하십시오.\n\n"
                + "\n".join(missing),
            )
            return False

        basis = data.get("성능점검기준구분", "연면적")

        if basis == "연면적":
            try:
                area = float(
                    str(data.get("연면적", ""))
                    .replace(",", "")
                    .strip()
                )
                if area <= 0:
                    raise ValueError
            except ValueError:
                QMessageBox.warning(
                    self,
                    "연면적 확인",
                    "연면적 기준 현장은 연면적을 0보다 큰 숫자로 입력하십시오.",
                )
                return False
        else:
            households = int(data.get("세대수", 0))

            if households <= 0:
                QMessageBox.warning(
                    self,
                    "세대수 확인",
                    "세대수 기준 현장은 세대수를 1세대 이상 입력하십시오.",
                )
                return False

        if self.inspection_start.date() > self.inspection_end.date():
            QMessageBox.warning(
                self,
                "점검기간 확인",
                "점검 종료일은 점검 시작일보다 빠를 수 없습니다.",
            )
            return False

        return True


    def load_site_data(self, data):
        self.site_name.setText(data.get("현장명", ""))
        self.address.setText(data.get("주소", ""))

        basis = data.get("성능점검기준구분", "")

        if not basis:
            basis = (
                "세대수"
                if int(data.get("세대수", 0) or 0) > 0
                and not str(data.get("연면적", "")).strip()
                else "연면적"
            )

        self.inspection_basis.setCurrentIndex(
            1 if basis == "세대수" else 0
        )

        use_index = self.building_use.findText(data.get("용도", "기타"))
        if use_index >= 0:
            self.building_use.setCurrentIndex(use_index)

        self.total_area.setText(str(data.get("연면적", "")))
        self.households.setValue(int(data.get("세대수", 0)))
        self.ground_floors.setValue(int(data.get("지상층수", 0)))
        self.basement_floors.setValue(int(data.get("지하층수", 0)))

        self.set_date_value(
            self.completion_date,
            data.get("준공일", ""),
        )
        self.set_date_value(
            self.reference_date,
            data.get("성능점검기준일", ""),
        )

        self.management_entity.setText(data.get("관리주체", ""))
        self.management_address.setText(data.get("관리주체주소", ""))
        self.representative.setText(data.get("대표자담당자", ""))
        self.phone.setText(data.get("전화번호", ""))
        self.maintenance_manager.setText(
            data.get("기계설비유지관리자", "")
        )

        grade_index = self.maintenance_grade.findText(
            data.get("유지관리자등급", "해당 없음")
        )
        if grade_index >= 0:
            self.maintenance_grade.setCurrentIndex(grade_index)

        self.maintenance_manager2.setText(
            data.get("기계설비유지관리자2", "")
        )

        grade_index2 = self.maintenance_grade2.findText(
            data.get("유지관리자등급2", "해당 없음")
        )
        if grade_index2 >= 0:
            self.maintenance_grade2.setCurrentIndex(grade_index2)

        self.set_date_value(
            self.manager1_appointment_date,
            data.get("유지관리자1선임일", ""),
        )
        self.set_date_value(
            self.manager1_education_date,
            data.get("유지관리자1교육수료일", ""),
        )
        self.set_date_value(
            self.manager2_appointment_date,
            data.get("유지관리자2선임일", ""),
        )
        self.set_date_value(
            self.manager2_education_date,
            data.get("유지관리자2교육수료일", ""),
        )
        self.maintenance_org.document().setPlainText(
            data.get("유지관리조직도", "")
        )
        org_cursor = QTextCursor(self.maintenance_org.document())
        org_cursor.movePosition(QTextCursor.Start)
        self.maintenance_org.setTextCursor(org_cursor)
        self.set_date_value(
            self.contract_start,
            data.get("계약시작일", data.get("점검시작일", "")),
        )
        self.set_date_value(
            self.contract_end,
            data.get("계약종료일", data.get("점검종료일", "")),
        )
        self.inspection_method.setCurrentText(
            data.get("점검방법", "성능점검업체 대행")
        )
        self.submit_authority.setText(
            data.get("제출관청", "")
        )

        self.set_date_value(
            self.inspection_start,
            data.get("점검시작일", ""),
        )
        self.set_date_value(
            self.inspection_end,
            data.get("점검종료일", ""),
        )
        self.set_date_value(
            self.report_date,
            data.get("보고서작성일", ""),
        )
