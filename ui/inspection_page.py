from datetime import datetime
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from inspection import (
    CRITERION_JUDGMENT_OPTIONS,
    INSPECTION_STATUS_OPTIONS,
    UNAVAILABLE_REASON_OPTIONS,
    criteria_judgment_warnings,
    derive_final_judgment_from_criteria,
    evaluate_criteria_completion,
    measurement_metadata_for,
    normalize_criteria_results,
)

from catalogs.equipment_subtypes import (
    CHILLER_SUBTYPES,
    chiller_subtype_info,
    normalize_chiller_subtype,
)
from inspection.applicability import (
    chiller_confirmation_guidance,
    evaluate_chiller_item_applicability,
    resolve_effective_applicability,
)


class InspectionPageMixin:

    _criterion_method_groups = (
        ("visual", "현장 육안확인", ("visual",)),
        (
            "measurement",
            "계측 및 작동시험",
            ("measurement", "operation_test"),
        ),
        (
            "document",
            "서류·성적서 확인",
            ("document", "existing_data", "bms"),
        ),
    )

    _criterion_method_labels = {
        "visual": "현장/육안 확인",
        "operation_test": "작동시험",
        "measurement": "계측",
        "document": "서류·성적서 확인",
        "existing_data": "기존 운전·계측자료 확인",
        "bms": "BMS/중앙감시반 확인",
    }
    _criterion_status_labels = {
        "checked": "점검완료",
        "unavailable": "확인불가",
        "not_applicable": "해당없음",
        "not_checked": "미점검",
        "unused": "미사용",
    }
    _criterion_judgment_labels = {
        "unset": "미판정",
        "pass": "적합",
        "fail": "부적합",
    }
    _criterion_reason_labels = {
        "equipment_stopped": "장비 정지",
        "access_impossible": "접근 불가",
        "measurement_point_missing": "계측지점 없음",
        "measurement_impossible": "계측 불가",
        "operating_condition_not_met": "운전조건 미충족",
        "document_unavailable": "자료 확인 불가",
        "safety_restriction": "안전상 점검 불가",
        "other": "기타",
    }

    @staticmethod
    def new_equipment_id():
        return str(uuid.uuid4())

    def equipment_id_for_register_row(self, row, create=False):
        item = self.equipment_register_table.item(row, 2)
        if item is None:
            return ""

        equipment_id = str(item.data(Qt.UserRole) or "").strip()
        if not equipment_id and create:
            equipment_id = self.new_equipment_id()
            item.setData(Qt.UserRole, equipment_id)
        return equipment_id

    def equipment_id_for_target_row(self, row):
        item = self.target_table.item(row, 1)
        if item is None:
            return ""
        return str(item.data(Qt.UserRole) or "").strip()

    def set_target_equipment_id(self, row, equipment_id):
        item = self.target_table.item(row, 1)
        if item is not None:
            item.setData(Qt.UserRole, str(equipment_id or "").strip())

    @staticmethod
    def equipment_id_for_inspection_record(rows):
        equipment_ids = {
            str(item.get("equipment_id", "") or "").strip()
            for item in (rows or [])
            if isinstance(item, dict)
            and str(item.get("equipment_id", "") or "").strip()
        }
        return next(iter(equipment_ids)) if len(equipment_ids) == 1 else ""

    def find_inspection_records_by_equipment_id(self, equipment_id):
        equipment_id = str(equipment_id or "").strip()
        if not equipment_id:
            return []
        return [
            (key, rows)
            for key, rows in self.inspection_results.items()
            if self.equipment_id_for_inspection_record(rows) == equipment_id
        ]

    def target_keys_for_equipment_id(self, equipment_id):
        equipment_id = str(equipment_id or "").strip()
        if not equipment_id:
            return []
        return [
            self.target_key_from_row(row)
            for row in range(self.target_table.rowCount())
            if self.equipment_id_for_target_row(row) == equipment_id
        ]

    def reconcile_inspection_result_equipment_ids(self):
        """구 프로젝트 결과를 메모리에서만 안전하게 장비 ID와 연결한다."""
        reconciled = dict(self.inspection_results)

        for old_key, rows in list(self.inspection_results.items()):
            if not isinstance(rows, list):
                continue

            row_ids = {
                str(item.get("equipment_id", "") or "").strip()
                for item in rows
                if isinstance(item, dict)
                and str(item.get("equipment_id", "") or "").strip()
            }
            if len(row_ids) > 1:
                continue

            stored_id = next(iter(row_ids), "")
            stored_id_exists = (
                self.register_row_for_equipment_id(stored_id) >= 0
                if stored_id
                else False
            )
            current_target = self.find_target_data_by_key(old_key)
            current_id = (
                str(current_target.get("equipment_id", "") or "").strip()
                if current_target
                else ""
            )

            destination_key = old_key
            effective_id = stored_id

            if stored_id_exists:
                matching_keys = self.target_keys_for_equipment_id(stored_id)
                if old_key in matching_keys:
                    destination_key = old_key
                elif len(matching_keys) == 1:
                    destination_key = matching_keys[0]
                else:
                    continue
            elif current_id:
                effective_id = current_id
            else:
                continue

            if destination_key != old_key and destination_key in reconciled:
                continue

            updated_rows = []
            for item in rows:
                if not isinstance(item, dict):
                    updated_rows.append(item)
                    continue
                updated = dict(item)
                updated["equipment_id"] = effective_id
                updated_rows.append(updated)

            if destination_key != old_key:
                reconciled.pop(old_key, None)
            reconciled[destination_key] = updated_rows

        self.inspection_results = reconciled

    def register_row_for_equipment_id(self, equipment_id, equipment_type=""):
        equipment_id = str(equipment_id or "").strip()
        if not equipment_id:
            return -1

        matches = []
        for row in range(self.equipment_register_table.rowCount()):
            if (
                equipment_type
                and self.register_combo_text(row, 0) != equipment_type
            ):
                continue
            if self.equipment_id_for_register_row(row) == equipment_id:
                matches.append(row)
        return matches[0] if len(matches) == 1 else -1

    def unique_register_row(self, equipment_type, management_number):
        equipment_type = str(equipment_type or "").strip()
        management_number = str(management_number or "").strip()
        if not equipment_type or not management_number:
            return -1

        matches = []
        for row in range(self.equipment_register_table.rowCount()):
            data = self.register_row_data(row)
            if (
                data.get("설비종류", "") == equipment_type
                and data.get("관리번호", "") == management_number
            ):
                matches.append(row)
        return matches[0] if len(matches) == 1 else -1

    def create_inspection_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("4. 장비대장·점검대상 선정·설비별 점검결과")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        company_label = QLabel(
            f"성능점검업체: {self._company_name}  |  아래 인원은 건축물 선임 유지관리자가 아니라 성능점검업체 책임·참여기술자입니다."
        )
        company_label.setStyleSheet(
            "padding: 8px; background: #eef6ff; border: 1px solid #8bb8e8;"
        )
        layout.addWidget(company_label)

        self.inspection_tabs = QTabWidget()
        self.inspection_tabs.currentChanged.connect(
            self.on_inspection_tab_changed
        )

        # 4-1 전체 장비대장
        register_tab = QWidget()
        register_layout = QVBoxLayout(register_tab)

        register_notice = QLabel(
            "관리번호는 설비종류별로 자동 부여되며 직접 수정할 수 있습니다. "
            "점검대상 선정 시 장비대장에서 원하는 관리번호를 선택합니다."
        )
        register_notice.setWordWrap(True)
        register_notice.setStyleSheet(
            "padding: 8px; background: #fff7d6; border: 1px solid #e6c65c;"
        )
        register_layout.addWidget(register_notice)

        register_buttons = QHBoxLayout()
        generate_button = QPushButton("설비현황 수량으로 장비대장 생성")
        add_button = QPushButton("장비 1건 추가")
        remove_button = QPushButton("선택 장비 삭제")

        generate_button.clicked.connect(self.generate_equipment_register)
        add_button.clicked.connect(self.add_equipment_register_row)
        remove_button.clicked.connect(self.remove_equipment_register_row)

        register_buttons.addWidget(generate_button)
        register_buttons.addWidget(add_button)
        register_buttons.addWidget(remove_button)
        register_buttons.addStretch()
        register_layout.addLayout(register_buttons)

        self.equipment_register_table = QTableWidget()
        self.equipment_register_table.setColumnCount(7)
        self.equipment_register_table.setHorizontalHeaderLabels(
            [
                "설비종류",
                "세부유형",
                "관리번호",
                "설치위치",
                "주요사양",
                "설치연도",
                "비고",
            ]
        )
        self.equipment_register_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.equipment_register_table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.equipment_register_table.verticalHeader().setVisible(False)
        self.equipment_register_table.setAlternatingRowColors(True)
        self.equipment_register_table.itemChanged.connect(
            self.on_equipment_register_changed
        )

        register_header = self.equipment_register_table.horizontalHeader()
        register_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        register_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        register_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        register_header.setSectionResizeMode(3, QHeaderView.Stretch)
        register_header.setSectionResizeMode(4, QHeaderView.Stretch)
        register_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        register_header.setSectionResizeMode(6, QHeaderView.Stretch)

        register_layout.addWidget(self.equipment_register_table)

        self.register_summary = QLabel("등록 장비 0건")
        self.register_summary.setStyleSheet(
            "padding: 7px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        register_layout.addWidget(self.register_summary)

        # 4-2 점검대상 선정
        target_tab = QWidget()
        target_layout = QVBoxLayout(target_tab)

        target_notice = QLabel(
            "설비현황의 점검수량만큼 선정행을 만들고, 금년도 점검번호와 실제 점검할 관리번호를 직접 선택합니다."
        )
        target_notice.setWordWrap(True)
        target_notice.setStyleSheet(
            "padding: 8px; background: #f0fdf4; border: 1px solid #86c89a;"
        )
        target_layout.addWidget(target_notice)

        target_buttons = QHBoxLayout()
        create_target_button = QPushButton("점검수량으로 선정표 생성")
        add_target_button = QPushButton("선정행 추가")
        remove_target_button = QPushButton("선택 선정행 삭제")
        refresh_button = QPushButton("장비정보 새로고침")

        create_target_button.clicked.connect(self.generate_target_selection_rows)
        add_target_button.clicked.connect(self.add_target_selection_row)
        remove_target_button.clicked.connect(self.remove_target_selection_row)
        refresh_button.clicked.connect(self.refresh_target_table)

        target_buttons.addWidget(create_target_button)
        target_buttons.addWidget(add_target_button)
        target_buttons.addWidget(remove_target_button)
        target_buttons.addWidget(refresh_button)
        target_buttons.addStretch()
        target_layout.addLayout(target_buttons)

        self.target_table = QTableWidget()
        self.target_table.setColumnCount(7)
        self.target_table.setHorizontalHeaderLabels(
            [
                "설비종류",
                "금년도 점검번호",
                "관리번호 선택",
                "설치위치",
                "주요사양",
                "설치연도",
                "입력상태",
            ]
        )
        self.target_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.target_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.target_table.verticalHeader().setVisible(False)
        self.target_table.setAlternatingRowColors(True)

        target_header = self.target_table.horizontalHeader()
        target_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(2, QHeaderView.Stretch)
        target_header.setSectionResizeMode(3, QHeaderView.Stretch)
        target_header.setSectionResizeMode(4, QHeaderView.Stretch)
        target_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        target_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)

        target_layout.addWidget(self.target_table)

        self.target_summary = QLabel("선정된 점검대상 0건")
        self.target_summary.setStyleSheet(
            "padding: 7px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        target_layout.addWidget(self.target_summary)

        # 4-3 설비별 점검내용
        detail_tab = QWidget()
        detail_layout = QVBoxLayout(detail_tab)

        detail_top = QGridLayout()
        self.detail_equipment_combo = QComboBox()
        self.detail_equipment_combo.currentIndexChanged.connect(
            self.on_detail_equipment_changed
        )

        self.detail_company_label = QLabel(self._company_name)
        self.detail_technicians_label = QLabel("")
        self.detail_equipment_info = QLabel("점검대상을 선택하십시오.")
        self.detail_equipment_info.setWordWrap(True)
        self.performance_cop_reference_label = QLabel("")
        self.performance_cop_reference_label.setWordWrap(True)
        self.performance_cop_reference_label.setStyleSheet(
            "padding: 7px; background: #eef6ff; border: 1px solid #8bb8e8;"
        )
        self.performance_cop_reference_label.setVisible(False)
        self.performance_cop_reference_title = QLabel("성능계산 참고")
        self.performance_cop_reference_title.setVisible(False)
        self.apply_performance_cop_button = QPushButton("참고 COP 적용")
        self.apply_performance_cop_button.setVisible(False)
        self.apply_performance_cop_button.setEnabled(False)
        self.apply_performance_cop_button.clicked.connect(
            self.apply_reference_cop_to_measurement
        )

        detail_top.addWidget(QLabel("점검대상 장비"), 0, 0)
        detail_top.addWidget(self.detail_equipment_combo, 0, 1, 1, 3)
        detail_top.addWidget(QLabel("점검업체"), 1, 0)
        detail_top.addWidget(self.detail_company_label, 1, 1)
        detail_top.addWidget(QLabel("성능점검 기술자"), 1, 2)
        detail_top.addWidget(self.detail_technicians_label, 1, 3)
        detail_top.addWidget(QLabel("장비정보"), 2, 0)
        detail_top.addWidget(self.detail_equipment_info, 2, 1, 1, 3)
        detail_top.addWidget(self.performance_cop_reference_title, 3, 0)
        detail_top.addWidget(
            self.performance_cop_reference_label, 3, 1, 1, 3
        )
        detail_top.addWidget(self.apply_performance_cop_button, 3, 4)
        detail_layout.addLayout(detail_top)

        self.detail_notice = QLabel(
            "육안·작동확인 항목은 확인내용만 입력하고, 실제 계측이 필요한 항목에만 "
            "설계·정격값과 측정값 입력칸이 활성화됩니다."
        )
        self.detail_notice.setWordWrap(True)
        self.detail_notice.setStyleSheet(
            "padding: 8px; background: #fff7d6; border: 1px solid #e6c65c;"
        )
        detail_layout.addWidget(self.detail_notice)

        self.detail_subtabs = QTabWidget()
        self.detail_judgment_tab = QWidget()
        self.detail_judgment_layout = QVBoxLayout(self.detail_judgment_tab)
        self.detail_judgment_layout.setContentsMargins(4, 4, 4, 4)
        self.criteria_detail_tab = QWidget()
        self.criteria_detail_layout = QVBoxLayout(self.criteria_detail_tab)
        self.criteria_detail_layout.setContentsMargins(4, 4, 4, 4)
        self.detail_subtabs.addTab(
            self.detail_judgment_tab, "점검내용·판정"
        )
        self.detail_subtabs.addTab(
            self.criteria_detail_tab, "점검기준별 수행결과"
        )
        self.detail_subtabs.setCurrentIndex(0)
        self.detail_subtabs.setTabEnabled(1, False)
        self.detail_subtabs.currentChanged.connect(
            self.on_detail_subtab_changed
        )
        detail_layout.addWidget(self.detail_subtabs, 1)

        self.inspection_detail_table = QTableWidget()
        self.inspection_detail_table.setColumnCount(14)
        self.inspection_detail_table.setHorizontalHeaderLabels(
            [
                "번호",
                "점검내용",
                "점검방법",
                "점검기준",
                "입력구분",
                "설계·정격값",
                "측정·확인값",
                "단위",
                "허용편차[%]",
                "편차율[%]",
                "판정",
                "사유·기술적 소견",
                "적용성",
                "수행결과",
            ]
        )
        self.inspection_detail_table.verticalHeader().setVisible(False)
        self.inspection_detail_table.verticalHeader().setSectionResizeMode(
            QHeaderView.Fixed
        )
        self.inspection_detail_table.verticalHeader().setDefaultSectionSize(34)
        self.inspection_detail_table.setAlternatingRowColors(True)

        detail_header = self.inspection_detail_table.horizontalHeader()
        detail_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(1, QHeaderView.Stretch)
        detail_header.setSectionResizeMode(2, QHeaderView.Interactive)
        detail_header.setSectionResizeMode(3, QHeaderView.Interactive)
        detail_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(9, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(11, QHeaderView.Stretch)
        detail_header.setSectionResizeMode(12, QHeaderView.ResizeToContents)
        detail_header.setSectionResizeMode(13, QHeaderView.ResizeToContents)
        detail_header.resizeSection(2, 190)
        detail_header.resizeSection(3, 280)
        # 점검방법 원문은 데이터와 보고서 모델에 그대로 유지하되, 4-3의
        # 현장 입력 화면에서는 반복 문구가 차지하는 폭을 점검내용/기준에 양보한다.
        self.inspection_detail_table.setColumnHidden(2, True)
        detail_header.setSectionResizeMode(1, QHeaderView.Interactive)
        detail_header.setSectionResizeMode(3, QHeaderView.Interactive)
        detail_header.setSectionResizeMode(11, QHeaderView.Interactive)
        detail_header.resizeSection(1, 240)
        detail_header.resizeSection(3, 460)
        detail_header.resizeSection(11, 280)

        self.inspection_detail_table.itemChanged.connect(
            self.on_inspection_measurement_changed
        )
        self.inspection_detail_table.itemChanged.connect(
            self.on_technical_opinion_item_changed
        )
        self.inspection_detail_table.currentCellChanged.connect(
            self.update_not_applicable_confirm_button
        )
        self.inspection_detail_table.currentCellChanged.connect(
            self.refresh_applicability_review_panel
        )
        self.inspection_detail_table.currentCellChanged.connect(
            self.refresh_performance_cop_reference
        )
        self.inspection_detail_table.currentCellChanged.connect(
            self.refresh_criteria_results_panel
        )
        self.inspection_detail_table.currentCellChanged.connect(
            self.refresh_technical_opinion_candidates
        )
        self.inspection_detail_table.cellDoubleClicked.connect(
            self.on_inspection_detail_double_clicked
        )

        self.inspection_detail_table.setWordWrap(False)
        self.inspection_detail_table.setMinimumHeight(320)
        self.detail_judgment_layout.addWidget(
            self.inspection_detail_table, 1
        )

        opinion_candidate_layout = QHBoxLayout()
        opinion_candidate_layout.addWidget(QLabel("기술적소견 후보"))
        self.technical_opinion_candidate_combo = QComboBox()
        self.technical_opinion_candidate_combo.setMinimumWidth(280)
        self.technical_opinion_candidate_combo.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon
        )
        self.technical_opinion_apply_button = QPushButton("선택 소견 적용")
        self.technical_opinion_apply_button.clicked.connect(
            self.apply_selected_technical_opinion
        )
        opinion_candidate_layout.addWidget(
            self.technical_opinion_candidate_combo, 1
        )
        opinion_candidate_layout.addWidget(
            self.technical_opinion_apply_button
        )
        self._technical_opinion_candidate_layout = opinion_candidate_layout

        self.criteria_target_summary_label = QLabel("")
        self.criteria_target_summary_label.setWordWrap(True)
        self.criteria_target_summary_label.setStyleSheet(
            "padding: 8px; background: #eef6ff; border: 1px solid #9cc2e5; "
            "font-weight: 600;"
        )
        self.criteria_detail_layout.addWidget(self.criteria_target_summary_label)

        self.criteria_groups_scroll = QScrollArea()
        self.criteria_groups_scroll.setWidgetResizable(True)
        self.criteria_groups_content = QWidget()
        self.criteria_groups_layout = QVBoxLayout(self.criteria_groups_content)
        self.criteria_groups_layout.setContentsMargins(6, 6, 6, 6)
        self.criteria_groups_scroll.setWidget(self.criteria_groups_content)
        self.criteria_detail_layout.addWidget(self.criteria_groups_scroll, 1)

        self.criteria_results_panel = QGroupBox("선택 점검항목 수행결과")
        criteria_panel_layout = QVBoxLayout(self.criteria_results_panel)
        self.criteria_completion_label = QLabel("완결성: 미점검")
        self.criteria_completion_label.setWordWrap(True)
        self.criteria_completion_label.setStyleSheet(
            "padding: 6px; background: #f7f7f7; border: 1px solid #d1d5db;"
        )
        self.criteria_warning_label = QLabel("")
        self.criteria_warning_label.setWordWrap(True)
        self.criteria_warning_label.setStyleSheet(
            "padding: 6px; background: #fff7d6; border: 1px solid #e6c65c;"
        )
        self.criteria_warning_label.setVisible(False)
        criteria_panel_layout.addWidget(self.criteria_completion_label)
        self.criteria_final_judgment_label = QLabel("점검내용 판정 : 미점검")
        self.criteria_final_judgment_label.setWordWrap(True)
        self.criteria_final_judgment_label.setStyleSheet(
            "padding: 10px; font-size: 15px; font-weight: 700; "
            "background: #f7f7f7; border: 2px solid #9ca3af;"
        )
        criteria_panel_layout.addWidget(self.criteria_final_judgment_label)
        criteria_panel_layout.addWidget(self.criteria_warning_label)

        criteria_bulk_layout = QHBoxLayout()
        criteria_bulk_layout.addWidget(QLabel("일괄 수행방법"))
        self.criteria_bulk_method = QComboBox()
        self.criteria_bulk_method.addItem("선택 안 함", "")
        for method, label, _legacy_methods in self._criterion_method_groups:
            self.criteria_bulk_method.addItem(label, method)
        criteria_bulk_layout.addWidget(self.criteria_bulk_method)
        self.criteria_bulk_pass_button = QPushButton(
            "미입력 점검기준 전체 적합"
        )
        self.criteria_bulk_pass_button.clicked.connect(
            self.mark_unset_criteria_pass
        )
        criteria_bulk_layout.addWidget(self.criteria_bulk_pass_button)
        self.criteria_equipment_bulk_pass_button = QPushButton(
            "현재 장비 미입력 점검기준 전체 적합"
        )
        self.criteria_equipment_bulk_pass_button.clicked.connect(
            self.mark_all_unset_criteria_pass_for_current_equipment
        )
        criteria_bulk_layout.addWidget(self.criteria_equipment_bulk_pass_button)
        self.criteria_reset_button = QPushButton("점검기준 전체 초기화")
        self.criteria_reset_button.clicked.connect(
            self.reset_current_criteria_results
        )
        criteria_bulk_layout.addWidget(self.criteria_reset_button)
        self.criteria_equipment_reset_button = QPushButton(
            "현재 장비 전체 수행결과 초기화"
        )
        self.criteria_equipment_reset_button.clicked.connect(
            self.reset_current_equipment_criteria_results
        )
        criteria_bulk_layout.addWidget(self.criteria_equipment_reset_button)
        criteria_bulk_layout.addStretch()
        criteria_panel_layout.addLayout(criteria_bulk_layout)

        self.criteria_results_scroll = QScrollArea()
        self.criteria_results_scroll.setWidgetResizable(True)
        self.criteria_results_scroll.setMinimumHeight(100)
        self.criteria_results_content = QWidget()
        self.criteria_results_layout = QVBoxLayout(
            self.criteria_results_content
        )
        self.criteria_results_layout.setContentsMargins(6, 6, 6, 6)
        self.criteria_results_layout.addStretch()
        self.criteria_results_scroll.setWidget(
            self.criteria_results_content
        )
        criteria_panel_layout.addWidget(self.criteria_results_scroll)

        self.criteria_item_opinion = QPlainTextEdit()
        self.criteria_item_opinion.setMaximumHeight(86)
        self.criteria_item_opinion.setPlaceholderText(
            "현재 점검항목 전체의 점검소견을 작성하십시오."
        )
        self.criteria_item_opinion.textChanged.connect(
            self.on_criteria_item_opinion_changed
        )
        criteria_panel_layout.addWidget(QLabel("점검소견"))
        criteria_panel_layout.addWidget(self.criteria_item_opinion)
        criteria_panel_layout.addLayout(
            self._technical_opinion_candidate_layout
        )
        self.criteria_results_panel.setVisible(False)
        self._criteria_group_buttons = {}

        self._criterion_result_editors = []
        self._criteria_results_by_row = {}
        self._criteria_results_should_save = set()
        self._criteria_auto_opinion_by_row = {}
        self._criteria_panel_row = -1
        self._loading_criteria_panel = False
        self._loading_criteria_item_opinion = False

        self.applicability_review_panel = QWidget()
        review_layout = QGridLayout(self.applicability_review_panel)
        review_layout.setContentsMargins(8, 6, 8, 6)
        self.applicability_review_title = QLabel("[확인필요 상세]")
        self.applicability_review_guide = QLabel(
            "확인필요 상태인 냉동기 점검항목을 선택하십시오."
        )
        self.applicability_review_guide.setWordWrap(True)
        self.applicability_review_result = QComboBox()
        self.applicability_review_result.addItem("선택하십시오", "")
        self.applicability_review_result.addItem(
            "적용 확인", "confirmed_applicable"
        )
        self.applicability_review_result.addItem(
            "비적용 확인", "confirmed_not_applicable"
        )
        self.applicability_review_result.addItem(
            "확인 계속 필요", "unresolved"
        )
        self.applicability_review_note = QLineEdit()
        self.applicability_review_note.setPlaceholderText(
            "확인한 설비구성·제조사 자료·추가 확인사항 등을 입력하십시오."
        )
        self.applicability_review_save_button = QPushButton("확인결과 저장")
        self.applicability_review_save_button.clicked.connect(
            self.save_applicability_review
        )
        review_layout.addWidget(self.applicability_review_title, 0, 0)
        review_layout.addWidget(self.applicability_review_guide, 0, 1, 1, 5)
        review_layout.addWidget(QLabel("확인결과"), 1, 0)
        review_layout.addWidget(self.applicability_review_result, 1, 1)
        review_layout.addWidget(QLabel("확인메모"), 1, 2)
        review_layout.addWidget(self.applicability_review_note, 1, 3, 1, 2)
        review_layout.addWidget(self.applicability_review_save_button, 1, 5)
        self.applicability_review_panel.setStyleSheet(
            "QWidget { background: #f7f7f7; }"
        )
        self.detail_judgment_layout.addWidget(
            self.applicability_review_panel
        )
        self.refresh_applicability_review_panel()

        detail_buttons = QHBoxLayout()
        save_detail_button = QPushButton("현재 장비 점검내용 저장")
        self.confirm_not_applicable_button = QPushButton("비적용 확인")
        self.confirm_not_applicable_button.setEnabled(False)
        save_detail_button.clicked.connect(self.save_current_inspection_detail)
        self.criteria_bulk_pass_button.setToolTip(
            "현재 선택 점검항목에서 미입력 상태인 criterion만 "
            "점검완료/적합으로 입력하고 종합 결과를 행 최종판정에 반영합니다."
        )
        self.confirm_not_applicable_button.clicked.connect(
            self.confirm_current_not_applicable
        )

        detail_buttons.addWidget(save_detail_button)
        detail_buttons.addWidget(self.confirm_not_applicable_button)
        detail_buttons.addStretch()
        self.detail_judgment_layout.addLayout(detail_buttons)

        self.inspection_tabs.addTab(register_tab, "4-1. 전체 장비대장")
        self.inspection_tabs.addTab(target_tab, "4-2. 점검대상 선정")
        self.inspection_tabs.addTab(detail_tab, "4-3. 설비별 점검내용")

        cause_tab = QWidget()
        cause_layout = QVBoxLayout(cause_tab)

        cause_notice = QLabel(
            "X 불합격 항목을 대상으로 이상현상 → 원인후보 → 확인방법 → "
            "최종원인 → 영향 → 개선방안 순으로 원인분석을 작성합니다. "
            "자동 초안은 책임기술자의 판단을 보조하는 자료이며 최종 원인은 현장 확인 후 확정하십시오."
        )
        cause_notice.setWordWrap(True)
        cause_notice.setStyleSheet(
            "padding: 8px; background: #fff7d6; border: 1px solid #e2c35b;"
        )
        cause_layout.addWidget(cause_notice)

        cause_buttons = QHBoxLayout()
        cause_generate = QPushButton("불합격 항목 원인분석표 생성")
        cause_generate.clicked.connect(self.refresh_cause_analysis_table)
        cause_apply = QPushButton("원인분석 결과를 기술적 소견에 반영")
        cause_apply.clicked.connect(self.apply_cause_analysis_to_inspection)
        cause_buttons.addWidget(cause_generate)
        cause_buttons.addWidget(cause_apply)
        cause_buttons.addStretch()
        cause_layout.addLayout(cause_buttons)

        self.cause_analysis_table = QTableWidget(0, 10)
        self.cause_analysis_table.setHorizontalHeaderLabels(
            [
                "대상설비",
                "점검항목",
                "이상현상",
                "원인후보",
                "원인 확인방법",
                "최종원인",
                "영향",
                "개선방안",
                "우선순위",
                "기술적 소견",
            ]
        )
        cause_header = self.cause_analysis_table.horizontalHeader()
        cause_header.setSectionResizeMode(QHeaderView.Stretch)
        cause_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        cause_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        cause_header.setSectionResizeMode(8, QHeaderView.ResizeToContents)
        self.cause_analysis_table.setWordWrap(True)
        cause_layout.addWidget(self.cause_analysis_table)

        self.inspection_tabs.addTab(cause_tab, "4-4. 원인분석")

        # 4-5 전년도 비교
        compare_tab = QWidget()
        compare_layout = QVBoxLayout(compare_tab)

        compare_notice = QLabel(
            "전년도 Python 프로젝트(.json)를 불러오면 동일 관리번호의 점검결과, "
            "주요 성능지표 및 최근 에너지 사용량을 금년도와 비교합니다. "
            "COP·효율·유효도 계열 지표가 전년도 대비 90% 미만이거나, "
            "에너지 사용량이 5% 이상 증가하면 원인 확인 대상으로 표시합니다."
        )
        compare_notice.setWordWrap(True)
        compare_notice.setStyleSheet(
            "padding: 8px; background: #eef6ff; border: 1px solid #9ec5e5;"
        )
        compare_layout.addWidget(compare_notice)

        compare_buttons = QHBoxLayout()
        load_previous_button = QPushButton("전년도 프로젝트 불러오기")
        load_previous_button.clicked.connect(self.load_previous_project)
        compare_button = QPushButton("전년도 비교 실행")
        compare_button.clicked.connect(self.refresh_previous_comparison)
        compare_buttons.addWidget(load_previous_button)
        compare_buttons.addWidget(compare_button)
        compare_buttons.addStretch()
        compare_layout.addLayout(compare_buttons)

        self.previous_project_label = QLabel("전년도 프로젝트 미선택")
        self.previous_project_label.setStyleSheet(
            "padding: 7px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        compare_layout.addWidget(self.previous_project_label)

        self.previous_compare_table = QTableWidget(0, 8)
        self.previous_compare_table.setHorizontalHeaderLabels(
            [
                "구분",
                "대상",
                "점검항목/지표",
                "전년도",
                "금년도",
                "변화",
                "판정",
                "검토의견",
            ]
        )
        compare_header = self.previous_compare_table.horizontalHeader()
        compare_header.setSectionResizeMode(QHeaderView.Stretch)
        compare_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        compare_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        compare_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.previous_compare_table.setWordWrap(True)
        compare_layout.addWidget(self.previous_compare_table)

        self.previous_compare_summary = QPlainTextEdit()
        self.previous_compare_summary.setReadOnly(True)
        self.previous_compare_summary.setMaximumHeight(115)
        self.previous_compare_summary.setPlaceholderText(
            "전년도 비교 후 주요 변화와 원인 확인 필요 항목을 요약합니다."
        )
        compare_layout.addWidget(self.previous_compare_summary)

        self.inspection_tabs.addTab(compare_tab, "4-5. 전년도 비교")

        # 4-6 성능계산
        calc_tab = QWidget()
        calc_layout = QVBoxLayout(calc_tab)

        calc_notice = QLabel(
            "설계값과 현장 측정값을 입력하면 냉동기 COP, 냉각탑 유효도, "
            "보일러 효율, 열교환 효율, 펌프 유량·양정, 공기조화기 풍량, "
            "연소 공기비 등을 자동 계산합니다. 자동판정은 기술검토 보조값이며 "
            "최종 판정은 운전조건·부하율·제조사 기준을 함께 검토하십시오."
        )
        calc_notice.setWordWrap(True)
        calc_notice.setStyleSheet(
            "padding: 8px; background: #f0fdf4; border: 1px solid #86c89a;"
        )
        calc_layout.addWidget(calc_notice)

        calc_top = QHBoxLayout()
        self.performance_calc_type = QComboBox()
        self.performance_calc_type.addItems(
            list(self._performance_calc_defs.keys())
        )
        self.performance_calc_type.currentTextChanged.connect(
            self.on_performance_calc_type_changed
        )

        self.performance_calc_equipment = QComboBox()
        self.performance_calc_equipment.currentIndexChanged.connect(
            self.on_performance_equipment_changed
        )

        self.performance_calc_tag = QLineEdit()
        self.performance_calc_tag.setPlaceholderText(
            "관리번호 또는 장비번호 예: CH-01"
        )

        calc_button = QPushButton("계산")
        calc_button.clicked.connect(self.calculate_performance_metric)
        save_calc_button = QPushButton("계산결과 저장")
        save_calc_button.clicked.connect(self.save_performance_calculation)
        new_calc_button = QPushButton("입력 초기화")
        new_calc_button.clicked.connect(self.clear_performance_calc_inputs)

        calc_top.addWidget(QLabel("계산종류"))
        calc_top.addWidget(self.performance_calc_type)
        calc_top.addWidget(QLabel("장비 선택"))
        calc_top.addWidget(self.performance_calc_equipment)
        calc_top.addWidget(QLabel("장비번호"))
        calc_top.addWidget(self.performance_calc_tag)
        calc_top.addWidget(calc_button)
        calc_top.addWidget(save_calc_button)
        calc_top.addWidget(new_calc_button)
        calc_layout.addLayout(calc_top)

        self.performance_calc_input_table = QTableWidget(0, 3)
        self.performance_calc_input_table.setHorizontalHeaderLabels(
            ["입력항목", "단위", "값"]
        )
        input_header = self.performance_calc_input_table.horizontalHeader()
        input_header.setSectionResizeMode(0, QHeaderView.Stretch)
        input_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        input_header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.performance_calc_input_table.verticalHeader().setVisible(False)
        calc_layout.addWidget(self.performance_calc_input_table)

        self.performance_calc_result_table = QTableWidget(0, 5)
        self.performance_calc_result_table.setHorizontalHeaderLabels(
            ["산출항목", "설계/기준값", "계산/측정값", "대비", "기술검토"]
        )
        result_header = self.performance_calc_result_table.horizontalHeader()
        result_header.setSectionResizeMode(0, QHeaderView.Stretch)
        result_header.setSectionResizeMode(1, QHeaderView.Stretch)
        result_header.setSectionResizeMode(2, QHeaderView.Stretch)
        result_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        result_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.performance_calc_result_table.verticalHeader().setVisible(False)
        calc_layout.addWidget(self.performance_calc_result_table)

        self.performance_calc_note = QLabel("")
        self.performance_calc_note.setWordWrap(True)
        self.performance_calc_note.setStyleSheet(
            "padding: 7px; background: #fff7d6; border: 1px solid #e6c65c;"
        )
        calc_layout.addWidget(self.performance_calc_note)

        self.performance_calc_saved_table = QTableWidget(0, 6)
        self.performance_calc_saved_table.setHorizontalHeaderLabels(
            ["종류", "장비번호", "핵심지표", "값", "판정", "비고"]
        )
        saved_header = self.performance_calc_saved_table.horizontalHeader()
        saved_header.setSectionResizeMode(QHeaderView.Stretch)
        saved_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        saved_header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        saved_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.performance_calc_saved_table.verticalHeader().setVisible(False)
        self.performance_calc_saved_table.cellDoubleClicked.connect(
            self.load_saved_performance_calculation
        )
        calc_layout.addWidget(self.performance_calc_saved_table)

        self.inspection_tabs.addTab(calc_tab, "4-6. 성능계산")
        self.on_performance_calc_type_changed()

        layout.addWidget(self.inspection_tabs)

        bottom_buttons = QHBoxLayout()
        previous_button = QPushButton("이전: 성능점검 기술자")
        previous_button.setMinimumHeight(40)
        previous_button.clicked.connect(lambda: self.menu.setCurrentRow(2))

        next_button = QPushButton("다음: 사진관리")
        next_button.setMinimumHeight(40)
        next_button.clicked.connect(self.go_to_photo_page)

        bottom_buttons.addWidget(previous_button)
        bottom_buttons.addStretch()
        bottom_buttons.addWidget(next_button)
        layout.addLayout(bottom_buttons)

        return page


    def generate_equipment_register(self, checked=False, confirm_replace=True):
        if self.equipment_register_table.rowCount() > 0 and confirm_replace:
            answer = QMessageBox.question(
                self,
                "장비대장 다시 생성",
                "현재 장비대장을 지우고 설비현황의 전체수량 기준으로 다시 생성하시겠습니까?",
            )
            if answer != QMessageBox.Yes:
                return

        reusable_ids = {}
        duplicate_keys = set()
        for row in range(self.equipment_register_table.rowCount()):
            existing = self.register_row_data(row)
            equipment_type = str(existing.get("설비종류", "")).strip()
            management_number = str(existing.get("관리번호", "")).strip()
            equipment_id = str(existing.get("equipment_id", "")).strip()
            if not equipment_type or not management_number or not equipment_id:
                continue
            key = (equipment_type, management_number)
            if key in reusable_ids:
                duplicate_keys.add(key)
            else:
                reusable_ids[key] = equipment_id
        for key in duplicate_keys:
            reusable_ids.pop(key, None)

        self.save_current_inspection_detail()
        self.equipment_register_table.setRowCount(0)
        self.target_table.setRowCount(0)
        self.inspection_results = {}
        generated = 0

        for row, equipment in enumerate(self._equipment_list):
            selected = (
                self.equipment_table.item(row, 0).checkState()
                == Qt.Checked
            )
            if not selected:
                continue

            total = self.parse_non_negative_integer(
                self.equipment_table.item(row, 3).text()
            )
            if total <= 0:
                continue

            count = 1 if equipment["unit"] == "식" else total
            prefix = self.equipment_code_prefix(equipment["name"])

            for number in range(1, count + 1):
                management_number = (
                    f"{prefix}-{number:02d}"
                    if equipment["unit"] == "대"
                    else f"{prefix}-01"
                )
                self.add_equipment_register_row(
                    {
                        "설비종류": equipment["name"],
                        "관리번호": management_number,
                        "equipment_id": reusable_ids.get(
                            (equipment["name"], management_number), ""
                        ),
                        "설치위치": "",
                        "주요사양": "",
                        "설치연도": "",
                        "비고": "",
                    }
                )
                generated += 1

        self.update_register_summary()

        if generated:
            self.status_label.setText(
                f"설비현황 기준으로 장비대장 {generated}건을 생성했습니다."
            )
        else:
            QMessageBox.warning(
                self,
                "장비대장 생성",
                "전체수량이 1 이상인 설비가 없습니다.",
            )

    def add_equipment_register_row(self, data=None):
        data = data or {}
        equipment_id = str(data.get("equipment_id", "") or "").strip()
        if not equipment_id:
            equipment_id = self.new_equipment_id()
        row = self.equipment_register_table.rowCount()

        self.equipment_register_table.blockSignals(True)
        self.equipment_register_table.insertRow(row)

        equipment_combo = QComboBox()
        equipment_combo.setEditable(True)
        equipment_combo.addItems([item["name"] for item in self._equipment_list])
        equipment_combo.setCurrentText(
            data.get("설비종류", self._equipment_list[0]["name"])
        )
        equipment_combo.currentTextChanged.connect(
            lambda text, combo=equipment_combo: (
                self.on_register_equipment_type_changed(combo, text)
            )
        )
        self.equipment_register_table.setCellWidget(row, 0, equipment_combo)

        subtype_combo = QComboBox()
        subtype_combo.currentIndexChanged.connect(
            lambda _index: (
                self.refresh_inspection_applicability(),
                self.refresh_performance_equipment_choices()
                if hasattr(self, "performance_calc_equipment")
                else None,
                self.refresh_performance_cop_reference()
                if hasattr(self, "performance_cop_reference_label")
                else None,
            )
        )
        self.equipment_register_table.setCellWidget(row, 1, subtype_combo)
        self.configure_register_subtype_combo(
            row,
            equipment_combo.currentText().strip(),
            data.get("세부유형", "unspecified"),
        )

        values = [
            data.get("관리번호", ""),
            data.get("설치위치", ""),
            data.get("주요사양", ""),
            data.get("설치연도", ""),
            data.get("비고", ""),
        ]

        for column, value in enumerate(values, start=2):
            item = QTableWidgetItem(str(value))
            if column == 2:
                item.setData(Qt.UserRole, equipment_id)
            self.equipment_register_table.setItem(row, column, item)

        self.equipment_register_table.blockSignals(False)
        self.update_register_summary()

    def configure_register_subtype_combo(
        self, row, equipment_type, subtype="unspecified"
    ):
        combo = self.equipment_register_table.cellWidget(row, 1)
        if combo is None:
            return

        combo.blockSignals(True)
        combo.clear()

        if equipment_type == "냉동기":
            for item in CHILLER_SUBTYPES:
                combo.addItem(item["label"], item["code"])
            code = normalize_chiller_subtype(subtype)
            index = combo.findData(code)
            combo.setCurrentIndex(max(index, 0))
            combo.setEnabled(True)
        else:
            combo.addItem("미적용", "")
            combo.setEnabled(False)

        combo.blockSignals(False)

    def on_register_equipment_type_changed(self, equipment_combo, text):
        for row in range(self.equipment_register_table.rowCount()):
            if self.equipment_register_table.cellWidget(row, 0) is equipment_combo:
                self.configure_register_subtype_combo(row, text)
                break
        self.update_register_summary()

    def register_subtype_code(self, row):
        combo = self.equipment_register_table.cellWidget(row, 1)
        if combo is None or not combo.isEnabled():
            return ""
        return normalize_chiller_subtype(combo.currentData())

    def remove_equipment_register_row(self):
        row = self.equipment_register_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self,
                "장비 선택",
                "삭제할 장비 행을 먼저 선택하십시오.",
            )
            return

        self.equipment_register_table.removeRow(row)
        self.update_register_summary()
        self.refresh_target_table()

    def on_equipment_register_changed(self, item):
        self.update_register_summary()
        if hasattr(self, "performance_calc_equipment"):
            self.refresh_performance_equipment_choices()
        if hasattr(self, "performance_cop_reference_label"):
            self.refresh_performance_cop_reference()

    def update_register_summary(self):
        total = self.equipment_register_table.rowCount()
        types = set()

        for row in range(total):
            equipment_type = self.register_combo_text(row, 0)
            if equipment_type:
                types.add(equipment_type)

        self.register_summary.setText(
            f"등록 장비 {total}건 | 설비종류 {len(types)}종"
        )

    def generate_target_selection_rows(self, checked=False, confirm_replace=True):
        if self.target_table.rowCount() > 0 and confirm_replace:
            answer = QMessageBox.question(
                self,
                "점검대상 선정표 다시 생성",
                "현재 선정표를 지우고 설비현황의 점검수량 기준으로 다시 생성하시겠습니까?",
            )
            if answer != QMessageBox.Yes:
                return

        reusable_targets = {}
        duplicate_target_keys = set()
        for row in range(self.target_table.rowCount()):
            target = self.target_row_data(row)
            equipment_id = self.equipment_id_for_target_row(row)
            if not equipment_id or self.register_row_for_equipment_id(
                equipment_id, target.get("설비종류", "")
            ) < 0:
                continue
            key = (
                target.get("설비종류", ""),
                str(target.get("점검번호", "")),
            )
            if key in reusable_targets:
                duplicate_target_keys.add(key)
            else:
                reusable_targets[key] = equipment_id
        for key in duplicate_target_keys:
            reusable_targets.pop(key, None)

        self.save_current_inspection_detail()
        self.target_table.setRowCount(0)
        generated = 0

        for row, equipment in enumerate(self._equipment_list):
            selected = (
                self.equipment_table.item(row, 0).checkState()
                == Qt.Checked
            )
            if not selected:
                continue

            inspection_count = self.parse_non_negative_integer(
                self.equipment_table.item(row, 6).text()
            )

            for number in range(1, inspection_count + 1):
                self.add_target_selection_row(
                    {
                        "설비종류": equipment["name"],
                        "점검번호": str(number),
                        "장비대장행": -1,
                        "equipment_id": reusable_targets.get(
                            (equipment["name"], str(number)), ""
                        ),
                    }
                )
                generated += 1

        self.refresh_target_table()

        if generated:
            self.status_label.setText(
                f"점검수량 기준으로 선정표 {generated}건을 생성했습니다."
            )
        else:
            QMessageBox.warning(
                self,
                "선정표 생성",
                "점검수량이 1건 이상인 설비가 없습니다.",
            )

    def add_target_selection_row(self, data=None):
        data = data or {}
        row = self.target_table.rowCount()
        self.target_table.insertRow(row)

        equipment_combo = QComboBox()
        equipment_combo.setEditable(True)
        equipment_combo.addItems([item["name"] for item in self._equipment_list])
        equipment_combo.setCurrentText(
            data.get("설비종류", self._equipment_list[0]["name"])
        )
        equipment_combo.currentTextChanged.connect(
            lambda _text, r=row: self.rebuild_target_source_combo(r)
        )
        self.target_table.setCellWidget(row, 0, equipment_combo)

        number_item = QTableWidgetItem(str(data.get("점검번호", row + 1)))
        number_item.setTextAlignment(Qt.AlignCenter)
        number_item.setData(
            Qt.UserRole, str(data.get("equipment_id", "") or "").strip()
        )
        self.target_table.setItem(row, 1, number_item)

        source_combo = QComboBox()
        source_combo.setEditable(True)
        source_combo.currentIndexChanged.connect(
            lambda _index, r=row: self.apply_target_source(r)
        )
        self.target_table.setCellWidget(row, 2, source_combo)

        for column in range(3, 7):
            item = QTableWidgetItem("")
            if column != 6:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.target_table.setItem(row, column, item)

        self.rebuild_target_source_combo(
            row,
            preferred_register_row=data.get("장비대장행", -1),
            preferred_equipment_id=data.get("equipment_id", ""),
            preferred_management_number=data.get("관리번호", ""),
        )

    def remove_target_selection_row(self):
        row = self.target_table.currentRow()
        if row < 0:
            QMessageBox.warning(
                self,
                "선정행 선택",
                "삭제할 선정행을 먼저 선택하십시오.",
            )
            return

        key = self.target_key_from_row(row)
        self.inspection_results.pop(key, None)
        self.target_table.removeRow(row)
        self.refresh_target_table()

    def rebuild_target_source_combo(
        self,
        target_row,
        preferred_register_row=-1,
        preferred_equipment_id=None,
        preferred_management_number="",
    ):
        if target_row < 0 or target_row >= self.target_table.rowCount():
            return

        equipment_widget = self.target_table.cellWidget(target_row, 0)
        source_combo = self.target_table.cellWidget(target_row, 2)

        if not equipment_widget or not source_combo:
            return

        equipment_type = equipment_widget.currentText().strip()
        stored_equipment_id = (
            self.equipment_id_for_target_row(target_row)
            if preferred_equipment_id is None
            else str(preferred_equipment_id or "").strip()
        )

        resolved_register_row = self.register_row_for_equipment_id(
            stored_equipment_id, equipment_type
        )
        if (
            resolved_register_row < 0
            and not stored_equipment_id
            and preferred_register_row not in (None, -1)
        ):
            try:
                candidate_row = int(preferred_register_row)
            except (TypeError, ValueError):
                candidate_row = -1
            if (
                0 <= candidate_row < self.equipment_register_table.rowCount()
                and self.register_combo_text(candidate_row, 0) == equipment_type
            ):
                resolved_register_row = candidate_row
        if resolved_register_row < 0 and preferred_management_number:
            resolved_register_row = self.unique_register_row(
                equipment_type, preferred_management_number
            )

        source_combo.blockSignals(True)
        source_combo.clear()
        source_combo.addItem("관리번호 선택", -1)

        preferred_index = 0

        for register_row in range(self.equipment_register_table.rowCount()):
            register_type = self.register_combo_text(register_row, 0)
            if register_type != equipment_type:
                continue

            data = self.register_row_data(register_row)
            label = (
                data["관리번호"]
                or f"{equipment_type}-{register_row + 1:02d}"
            )
            source_combo.addItem(label, register_row)

            if register_row == resolved_register_row:
                preferred_index = source_combo.count() - 1

        source_combo.setCurrentIndex(preferred_index)
        source_combo.blockSignals(False)
        self.apply_target_source(target_row)

    def apply_target_source(self, target_row):
        if target_row < 0 or target_row >= self.target_table.rowCount():
            return

        source_combo = self.target_table.cellWidget(target_row, 2)
        if not source_combo:
            return

        register_row = source_combo.currentData()

        if register_row is None or int(register_row) < 0:
            self.set_target_equipment_id(target_row, "")
            for column in range(3, 6):
                self.target_table.item(target_row, column).setText("")
            self.target_table.item(target_row, 6).setText("관리번호 미선택")
        else:
            data = self.register_row_data(int(register_row))
            self.set_target_equipment_id(
                target_row, data.get("equipment_id", "")
            )
            values = [
                data["설치위치"],
                data["주요사양"],
                data["설치연도"],
            ]

            for offset, value in enumerate(values, start=3):
                self.target_table.item(target_row, offset).setText(str(value))

            self.target_table.item(target_row, 6).setText(
                "점검내용 입력완료"
                if self.target_key_from_row(target_row)
                in self.inspection_results
                else "점검내용 미입력"
            )

        self.update_target_summary()

    def refresh_target_table(self):
        self.save_current_inspection_detail()

        for row in range(self.target_table.rowCount()):
            self.apply_target_source(row)

        self.update_target_summary()
        self.populate_detail_equipment_combo()

    def update_target_summary(self):
        total = self.target_table.rowCount()
        selected = 0

        for row in range(total):
            source_combo = self.target_table.cellWidget(row, 2)
            if source_combo and source_combo.currentData() not in (None, -1):
                selected += 1

        self.target_summary.setText(
            f"선정행 {total}건 | 관리번호 선택완료 {selected}건 | 미선택 {total - selected}건"
        )

    def populate_detail_equipment_combo(self, target_rows=None):
        self.save_current_inspection_detail()

        current_key = self.detail_equipment_combo.currentData()
        self.detail_equipment_combo.blockSignals(True)
        self.detail_equipment_combo.clear()

        for row in range(self.target_table.rowCount()):
            equipment_type = self.target_combo_text(row, 0)
            inspection_number = self.table_item_text(
                self.target_table, row, 1
            )
            source_combo = self.target_table.cellWidget(row, 2)
            register_row = source_combo.currentData() if source_combo else -1

            if register_row in (None, -1):
                label = (
                    f"{equipment_type} | 점검번호 {inspection_number} | 관리번호 미선택"
                )
            else:
                register_data = self.register_row_data(int(register_row))
                label = (
                    f"{equipment_type} | 점검번호 {inspection_number} | "
                    f"{register_data['관리번호']}"
                )

            key = self.target_key_from_row(row)
            self.detail_equipment_combo.addItem(label, key)

        if current_key:
            index = self.detail_equipment_combo.findData(current_key)
            if index >= 0:
                self.detail_equipment_combo.setCurrentIndex(index)

        self.detail_equipment_combo.blockSignals(False)

        if self.detail_equipment_combo.count() > 0:
            self.on_detail_equipment_changed(
                self.detail_equipment_combo.currentIndex()
            )
        else:
            self.inspection_detail_table.setRowCount(0)
            self.detail_equipment_info.setText("점검대상을 선정하십시오.")
            self.refresh_performance_cop_reference()

    def on_inspection_tab_changed(self, index):
        if index == 1:
            self.refresh_target_table()
        elif index == 2:
            self.refresh_target_table()
            self.detail_technicians_label.setText(
                ", ".join(self.selected_technician_names())
            )

    def on_detail_equipment_changed(self, index):
        self.save_current_inspection_detail()

        key = self.detail_equipment_combo.itemData(index)
        if not key:
            self.current_detail_equipment_key = None
            self.inspection_detail_table.setRowCount(0)
            self.refresh_criteria_results_panel(-1)
            self.refresh_performance_cop_reference()
            return

        self.current_detail_equipment_key = key
        target_data = self.find_target_data_by_key(key)

        if not target_data:
            self.inspection_detail_table.setRowCount(0)
            self.refresh_criteria_results_panel(-1)
            self.refresh_performance_cop_reference()
            return

        self.detail_equipment_info.setText(
            f"설비종류: {target_data['설비종류']} | "
            f"금년도 점검번호: {target_data['점검번호']} | "
            f"관리번호: {target_data['관리번호'] or '-'} | "
            f"위치: {target_data['설치위치'] or '-'} | "
            f"주요사양: {target_data['주요사양'] or '-'} | "
            f"설치연도: {target_data['설치연도'] or '-'}"
        )

        self.load_equipment_inspection_detail(
            key, target_data["설비종류"]
        )
        self.refresh_performance_cop_reference()

    def criteria_for_detail_row(self, row):
        items = getattr(self, "_current_detail_inspection_items", [])
        if not isinstance(row, int) or row < 0 or row >= len(items):
            return []
        return measurement_metadata_for(items[row]).get("criteria", [])

    def _clear_criteria_results_panel(self):
        layout = self.criteria_results_layout
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._criterion_result_editors = []

    def _mark_criteria_results_changed(self, *_args):
        if self._loading_criteria_panel or self._criteria_panel_row < 0:
            return
        self._criteria_results_should_save.add(self._criteria_panel_row)
        self.refresh_criteria_completion_summary()

    @staticmethod
    def combined_criterion_evidence(values):
        notes = []
        seen = set()
        for value in values or []:
            note = str(value.get("evidence_note", "") or "").strip()
            if not note or note in seen:
                continue
            seen.add(note)
            if note[-1:] not in {".", "!", "?", "。"}:
                note += "."
            notes.append(note)
        return " ".join(notes)

    def sync_criterion_opinion(self, row, values):
        # New UI uses the inspection row's existing 기술적소견 as the single
        # item-level opinion source.  Legacy per-criterion evidence remains in
        # criteria_results but is never copied over the user's row opinion.
        return False

    def on_criteria_item_opinion_changed(self):
        if self._loading_criteria_item_opinion:
            return
        row = getattr(self, "_criteria_panel_row", -1)
        if row < 0 or row >= self.inspection_detail_table.rowCount():
            return
        opinion = self.criteria_item_opinion.toPlainText()
        item = self.inspection_detail_table.item(row, 11)
        if item is None:
            item = QTableWidgetItem("")
            self.inspection_detail_table.setItem(row, 11, item)
        if item.text() != opinion:
            item.setText(opinion)
        item.setToolTip(opinion)
        self.refresh_technical_opinion_candidates(row)

    def set_item_level_opinion(self, row, opinion):
        """Update the one shared item opinion in both 4-3 sub-tabs."""
        if row < 0 or row >= self.inspection_detail_table.rowCount():
            return False
        text = str(opinion or "")
        item = self.inspection_detail_table.item(row, 11)
        if item is None:
            item = QTableWidgetItem("")
            self.inspection_detail_table.setItem(row, 11, item)
        changed = item.text() != text
        if changed:
            item.setText(text)
        item.setToolTip(text)
        if row == getattr(self, "_criteria_panel_row", -1):
            self._loading_criteria_item_opinion = True
            try:
                if self.criteria_item_opinion.toPlainText() != text:
                    self.criteria_item_opinion.setPlainText(text)
            finally:
                self._loading_criteria_item_opinion = False
        return changed

    def ensure_default_pass_item_opinion(self, row):
        combo = self.inspection_detail_table.cellWidget(row, 10)
        item = self.inspection_detail_table.item(row, 11)
        if (
            combo is None
            or combo.currentText() != "○ 합격"
            or (item is not None and item.text().strip())
        ):
            return False
        return self.set_item_level_opinion(row, self.default_pass_reason(row))

    def sync_final_judgment_from_criteria(self, row, criteria, values):
        if row not in self._criteria_results_should_save:
            return None
        derived = derive_final_judgment_from_criteria(criteria, values)
        if not derived:
            return None
        combo = self.inspection_detail_table.cellWidget(row, 10)
        if combo is not None and combo.currentText() != derived:
            combo.setCurrentText(derived)
        return derived

    def _update_criterion_editor_visibility(self, editor):
        unavailable = (
            editor["status"].currentData() == "unavailable"
        )
        editor["reason_label"].setVisible(unavailable)
        editor["reason"].setVisible(unavailable)
        editor["reason"].setEnabled(unavailable)

        checked = editor["status"].currentData() == "checked"
        if not checked and editor["judgment"].currentData() != "unset":
            editor["judgment"].blockSignals(True)
            editor["judgment"].setCurrentIndex(
                editor["judgment"].findData("unset")
            )
            editor["judgment"].blockSignals(False)
        editor["judgment"].setEnabled(checked)

    def _criterion_editor_changed(self, editor):
        self._update_criterion_editor_visibility(editor)
        self._mark_criteria_results_changed()

    def _criterion_editor_value(self, editor, index, criterion):
        performed_methods = []
        original_methods = set(editor.get("original_methods", []))
        for key, _label, legacy_methods in self._criterion_method_groups:
            if not editor["method_groups"][key].isChecked():
                continue
            preserved = [
                method for method in legacy_methods if method in original_methods
            ]
            performed_methods.extend(preserved or [key])
        return {
            "criterion_index": index,
            "criterion_name": str(criterion.get("name", "") or ""),
            "performed_methods": performed_methods,
            "inspection_status": editor["status"].currentData(),
            "criterion_judgment": editor["judgment"].currentData(),
            "unavailable_reason": (
                editor["reason"].currentData()
                if editor["status"].currentData() == "unavailable"
                else ""
            ),
            "substitution": dict(editor.get("original_substitution", {})),
            "evidence_note": str(
                editor.get("original_evidence_note", "") or ""
            ),
        }

    def mark_unset_criteria_pass(self):
        """Mark only untouched criteria on the currently open item as pass."""
        row = getattr(self, "_criteria_panel_row", -1)
        criteria = self.criteria_for_detail_row(row)
        editors = getattr(self, "_criterion_result_editors", [])
        if row < 0 or not criteria or len(editors) != len(criteria):
            return 0

        selected_method = self.criteria_bulk_method.currentData() or ""
        changed = 0
        self._loading_criteria_panel = True
        try:
            for editor in editors:
                if (
                    editor["status"].currentData() != "not_checked"
                    or editor["judgment"].currentData() != "unset"
                ):
                    continue
                editor["status"].setCurrentIndex(
                    editor["status"].findData("checked")
                )
                editor["judgment"].setCurrentIndex(
                    editor["judgment"].findData("pass")
                )
                if selected_method:
                    editor["method_groups"][selected_method].setChecked(True)
                self._update_criterion_editor_visibility(editor)
                changed += 1
        finally:
            self._loading_criteria_panel = False

        if changed:
            self._criteria_results_should_save.add(row)
            self.store_current_criteria_results()
            self.refresh_criteria_completion_summary()
            self.ensure_default_pass_item_opinion(row)
            self.status_label.setText(
                f"현재 점검항목의 미입력 점검기준 {changed}개를 적합으로 처리했습니다. "
                "종합 결과를 행 최종판정에 반영했습니다."
            )
        else:
            self.status_label.setText(
                "현재 점검항목에 not_checked + unset 상태의 점검기준이 없습니다."
            )
        return changed

    def mark_all_unset_criteria_pass_for_current_equipment(self):
        """Mark untouched criteria across only the currently selected target."""
        self.store_current_criteria_results()
        selected_row = self.inspection_detail_table.currentRow()
        self._criteria_panel_row = -1
        selected_method = self.criteria_bulk_method.currentData() or ""
        changed = 0
        changed_rows = []
        for row in range(self.inspection_detail_table.rowCount()):
            criteria = self.criteria_for_detail_row(row)
            if not criteria:
                continue
            values = normalize_criteria_results(
                criteria, self._criteria_results_by_row.get(row, [])
            )
            row_changed = False
            for value in values:
                if (
                    value.get("inspection_status") != "not_checked"
                    or value.get("criterion_judgment") != "unset"
                ):
                    continue
                value["inspection_status"] = "checked"
                value["criterion_judgment"] = "pass"
                if selected_method and not value.get("performed_methods"):
                    value["performed_methods"] = [selected_method]
                changed += 1
                row_changed = True
            if not row_changed:
                continue
            self._criteria_results_by_row[row] = normalize_criteria_results(
                criteria, values
            )
            self._criteria_results_should_save.add(row)
            changed_rows.append(row)
            self.sync_criterion_opinion(row, values)
            self.sync_final_judgment_from_criteria(row, criteria, values)
            self.ensure_default_pass_item_opinion(row)
            self.update_row_source_of_truth_edit_policy(row)
            self.refresh_criterion_summary_cell(row)

        if changed_rows:
            # The visible editors still contain the pre-bulk values.  Detach
            # them before rebuilding so refresh cannot write those stale
            # controls back over the just-updated selected row.
            self._criteria_panel_row = -1
            self.refresh_criteria_results_panel(selected_row)
            self.rebuild_criteria_groups(selected_row)
            self.status_label.setText(
                f"현재 장비의 미입력 점검기준 {changed}개를 적합으로 처리했습니다. "
                "기존 수행결과와 작성 소견은 덮어쓰지 않았으며, "
                "빈 소견에만 기본 정상 소견을 입력했습니다."
            )
        else:
            self.refresh_criteria_results_panel(selected_row)
            self.status_label.setText(
                "현재 장비에 not_checked + unset 상태의 점검기준이 없습니다."
            )
        return changed

    def reset_current_equipment_criteria_results(self):
        """Reset criterion records for this target after an explicit warning."""
        rows = [
            row
            for row in range(self.inspection_detail_table.rowCount())
            if self.criteria_for_detail_row(row)
        ]
        if not rows:
            return False
        answer = QMessageBox.question(
            self,
            "현재 장비 수행결과 전체 초기화",
            "현재 장비의 모든 점검기준 수행결과를 초기화하시겠습니까?\n\n"
            "수행방법·수행상태·criterion 판정이 초기화됩니다. "
            "항목 점검소견과 과거 criterion 증빙기록은 보존됩니다. "
            "메인 판정은 미점검으로 다시 산출되며 기존 RCA 작성 내용은 삭제하지 않습니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False
        selected_row = self.inspection_detail_table.currentRow()
        self._criteria_panel_row = -1
        for row in rows:
            criteria = self.criteria_for_detail_row(row)
            values = normalize_criteria_results(
                criteria, self._criteria_results_by_row.get(row, [])
            )
            for value in values:
                value["performed_methods"] = []
                value["inspection_status"] = "not_checked"
                value["criterion_judgment"] = "unset"
                value["unavailable_reason"] = ""
            self._criteria_results_by_row[row] = values
            self._criteria_results_should_save.add(row)
            self._criteria_auto_opinion_by_row.pop(row, None)
            self.sync_final_judgment_from_criteria(row, criteria, values)
            self.update_row_source_of_truth_edit_policy(row)
            self.refresh_criterion_summary_cell(row)
        self._criteria_panel_row = -1
        self.refresh_criteria_results_panel(selected_row)
        self.rebuild_criteria_groups(selected_row)
        self.status_label.setText(
            "현재 장비의 점검기준 수행결과를 초기화했습니다. "
            "행 판정은 미점검으로 다시 산출했습니다."
        )
        return True

    def reset_current_criteria_results(self):
        """Reset only criterion execution data for the currently open item."""
        row = getattr(self, "_criteria_panel_row", -1)
        criteria = self.criteria_for_detail_row(row)
        editors = getattr(self, "_criterion_result_editors", [])
        if row < 0 or not criteria or len(editors) != len(criteria):
            return False

        item_name = self.table_item_text(
            self.inspection_detail_table, row, 1
        )
        answer = QMessageBox.question(
            self,
            "점검기준 수행결과 초기화",
            f"현재 점검항목 '{item_name}'의 점검기준 수행결과를 모두 초기화하시겠습니까?\n\n"
            "수행상태·criterion 판정·수행방법을 초기화하며 "
            "행 최종판정은 미점검으로 갱신됩니다. "
            "항목 점검소견과 과거 criterion 증빙기록은 보존됩니다.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return False

        self._loading_criteria_panel = True
        try:
            for editor in editors:
                for checkbox in editor["method_groups"].values():
                    checkbox.setChecked(False)
                editor["status"].setCurrentIndex(
                    editor["status"].findData("not_checked")
                )
                editor["judgment"].setCurrentIndex(
                    editor["judgment"].findData("unset")
                )
                editor["reason"].setCurrentIndex(
                    editor["reason"].findData("")
                )
                self._update_criterion_editor_visibility(editor)
        finally:
            self._loading_criteria_panel = False

        self._criteria_results_should_save.add(row)
        self.store_current_criteria_results()
        self.refresh_criteria_completion_summary()
        self.status_label.setText(
            "현재 점검항목의 점검기준 수행결과를 초기화했습니다. "
            "행 최종판정은 미점검으로 갱신했습니다."
        )
        return True

    def store_current_criteria_results(self):
        row = getattr(self, "_criteria_panel_row", -1)
        criteria = self.criteria_for_detail_row(row)
        editors = getattr(self, "_criterion_result_editors", [])
        if row < 0 or not criteria or len(editors) != len(criteria):
            return
        values = [
            self._criterion_editor_value(editor, index, criterion)
            for index, (editor, criterion) in enumerate(
                zip(editors, criteria)
            )
        ]
        self._criteria_results_by_row[row] = normalize_criteria_results(
            criteria, values
        )

    def current_detail_final_judgment(self, row=None):
        row = self._criteria_panel_row if row is None else row
        combo = self.inspection_detail_table.cellWidget(row, 10)
        return combo.currentText() if combo is not None else "미점검"

    def update_row_source_of_truth_edit_policy(self, row):
        """Use derived display values only after criterion recording starts."""
        active = (
            bool(self.criteria_for_detail_row(row))
            and row in self._criteria_results_should_save
        )
        combo = self.inspection_detail_table.cellWidget(row, 10)
        if combo is not None:
            combo.setEnabled(not active)
            combo.setToolTip(
                "점검기준별 수행결과에서 자동 산출됩니다."
                if active
                else "수행기록이 없는 항목은 기존 방식으로 직접 판정할 수 있습니다."
            )
        opinion = self.inspection_detail_table.item(row, 11)
        if opinion is not None:
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if not active:
                flags |= Qt.ItemIsEditable
            opinion.setFlags(flags)
            opinion.setToolTip(
                opinion.text()
                + (
                    "\n수행결과 탭의 항목 단위 점검소견과 동일한 값입니다."
                    if active
                    else ""
                )
            )

    def refresh_criteria_completion_summary(self, *_args):
        if self._loading_criteria_panel:
            return
        row = getattr(self, "_criteria_panel_row", -1)
        criteria = self.criteria_for_detail_row(row)
        editors = getattr(self, "_criterion_result_editors", [])
        if not criteria or len(editors) != len(criteria):
            return

        values = [
            self._criterion_editor_value(editor, index, criterion)
            for index, (editor, criterion) in enumerate(
                zip(editors, criteria)
            )
        ]
        values = normalize_criteria_results(criteria, values)
        self._criteria_results_by_row[row] = values
        self.sync_criterion_opinion(row, values)
        self.sync_final_judgment_from_criteria(row, criteria, values)
        self.update_row_source_of_truth_edit_policy(row)
        completion = evaluate_criteria_completion(criteria, values)
        state_label = {
            "complete": "완료",
            "incomplete": "미완료",
            "review_required": "확인필요",
            "all_not_applicable": "전체 해당없음",
            "no_criteria": "기준 없음",
        }[completion["state"]]
        self.criteria_completion_label.setText(
            f"완결성: {state_label} | "
            f"적합 {completion['pass']} / 부적합 {completion['fail']} / "
            f"미판정 {completion['unset_judgment']} / "
            f"미점검 {completion['not_checked']} / "
            f"확인불가 {completion['unavailable']} / "
            f"해당없음 {completion['not_applicable']} / "
            f"미사용 {completion['unused']}"
        )
        summary_color = {
            "complete": "#dcfce7",
            "incomplete": "#f7f7f7",
            "review_required": "#fff7d6",
            "all_not_applicable": "#eef6ff",
            "no_criteria": "#f7f7f7",
        }[completion["state"]]
        self.criteria_completion_label.setStyleSheet(
            f"padding: 6px; background: {summary_color}; "
            "border: 1px solid #d1d5db;"
        )
        final_judgment = self.current_detail_final_judgment(row) or "미점검"
        final_color = {
            "○ 합격": "#dcfce7",
            "X 불합격": "#fee2e2",
            "/ 해당없음": "#eef6ff",
            "미사용": "#f3f4f6",
        }.get(final_judgment, "#fff7d6")
        self.criteria_final_judgment_label.setText(
            f"점검내용 판정 : {final_judgment}  |  "
            f"criterion {completion['total']}개 중 적합 {completion['pass']} / "
            f"부적합 {completion['fail']}"
        )
        self.criteria_final_judgment_label.setStyleSheet(
            f"padding: 10px; font-size: 15px; font-weight: 700; "
            f"background: {final_color}; border: 2px solid #9ca3af;"
        )

        warnings = criteria_judgment_warnings(
            criteria,
            values,
            self.current_detail_final_judgment(row),
        )
        self.criteria_warning_label.setText(
            "\n".join(f"• {warning}" for warning in warnings)
        )
        self.criteria_warning_label.setVisible(bool(warnings))
        self.refresh_criterion_summary_cell(row)

    def criterion_summary_text(self, row):
        criteria = self.criteria_for_detail_row(row)
        if not criteria:
            return "기준 없음"
        if row not in self._criteria_results_should_save:
            return "기록없음"
        values = self._criteria_results_by_row.get(row, [])
        summary = evaluate_criteria_completion(criteria, values)
        if summary["fail"]:
            return f"부적합 {summary['fail']}"
        if summary["unavailable"]:
            return f"확인불가 {summary['unavailable']}"
        if summary["unset_judgment"]:
            return f"미판정 {summary['unset_judgment']}"
        if summary["not_checked"]:
            completed = summary["checked"] + summary["not_applicable"]
            return f"{completed}/{summary['total']} 완료"
        if summary["unused"]:
            return f"미사용 {summary['unused']}"
        if summary["state"] == "all_not_applicable":
            return "해당없음"
        if summary["pass"] == summary["applicable"]:
            return f"{summary['pass']}/{summary['total']} 적합"
        return f"{summary['checked']}/{summary['total']} 완료"

    def criteria_group_header_text(self, row):
        items = getattr(self, "_current_detail_inspection_items", [])
        if row < 0 or row >= len(items):
            return ""
        item = items[row]
        criteria = self.criteria_for_detail_row(row)
        final_judgment = self.current_detail_final_judgment(row) or "미점검"
        summary = self.criterion_summary_text(row)
        warning_suffix = ""
        if criteria:
            values = self._criteria_results_by_row.get(row, [])
            warnings = criteria_judgment_warnings(
                criteria, values, final_judgment
            )
            if warnings:
                warning_suffix = " · 확인필요"
        return (
            f"{item.get('no', row + 1)}. {item.get('name', '')} | "
            f"최종 {final_judgment} | 기준 {len(criteria)} | "
            f"{summary}{warning_suffix}"
        )

    def refresh_criteria_target_summary(self):
        items = getattr(self, "_current_detail_inspection_items", [])
        totals = {
            "criteria": 0,
            "pass": 0,
            "fail": 0,
            "unset": 0,
            "not_checked": 0,
            "unavailable": 0,
        }
        for row in range(len(items)):
            criteria = self.criteria_for_detail_row(row)
            if not criteria:
                continue
            result = evaluate_criteria_completion(
                criteria, self._criteria_results_by_row.get(row, [])
            )
            totals["criteria"] += result["total"]
            totals["pass"] += result["pass"]
            totals["fail"] += result["fail"]
            totals["unset"] += result["unset_judgment"]
            totals["not_checked"] += result["not_checked"]
            totals["unavailable"] += result["unavailable"]
        equipment_label = self.detail_equipment_combo.currentText() or "현재 장비"
        self.criteria_target_summary_label.setText(
            f"{equipment_label} | 점검항목 {len(items)} | "
            f"criterion {totals['criteria']} | 적합 {totals['pass']} | "
            f"부적합 {totals['fail']} | 미판정 {totals['unset']} | "
            f"미점검 {totals['not_checked']} | 확인불가 {totals['unavailable']}"
        )

    def refresh_criteria_group_headers(self):
        for row, button in getattr(self, "_criteria_group_buttons", {}).items():
            button.setText(self.criteria_group_header_text(row))
            button.setChecked(row == self._criteria_panel_row)
        self.refresh_criteria_target_summary()

    def rebuild_criteria_groups(self, focus_row=None, expand=True):
        if not hasattr(self, "criteria_groups_layout"):
            return
        self.criteria_results_panel.setParent(None)
        while self.criteria_groups_layout.count():
            child = self.criteria_groups_layout.takeAt(0)
            widget = child.widget()
            if widget is not None and widget is not self.criteria_results_panel:
                widget.deleteLater()
        self._criteria_group_buttons = {}
        items = getattr(self, "_current_detail_inspection_items", [])
        if not items:
            self.criteria_groups_layout.addWidget(QLabel("점검대상을 선택하십시오."))
            self.criteria_groups_layout.addStretch()
            self.detail_subtabs.setTabEnabled(1, False)
            self.refresh_criteria_target_summary()
            return

        self.detail_subtabs.setTabEnabled(1, True)
        selected = (
            focus_row
            if isinstance(focus_row, int) and 0 <= focus_row < len(items)
            else self.inspection_detail_table.currentRow()
        )
        for row in range(len(items)):
            button = QPushButton(self.criteria_group_header_text(row))
            button.setCheckable(True)
            button.setChecked(expand and row == selected)
            button.setStyleSheet("text-align: left; padding: 8px;")
            button.clicked.connect(
                lambda checked=False, r=row: self.toggle_criteria_group(r, checked)
            )
            self._criteria_group_buttons[row] = button
            self.criteria_groups_layout.addWidget(button)
            if expand and row == selected:
                self.criteria_groups_layout.addWidget(self.criteria_results_panel)
        self.criteria_groups_layout.addStretch()
        self.refresh_criteria_target_summary()
        if expand and selected in self._criteria_group_buttons:
            self.criteria_groups_scroll.ensureWidgetVisible(
                self._criteria_group_buttons[selected], 0, 24
            )

    def toggle_criteria_group(self, row, expanded):
        if expanded:
            self.select_criteria_group(row)
            return
        self.criteria_results_panel.setParent(None)
        self.rebuild_criteria_groups(row, expand=False)

    def select_criteria_group(self, row):
        if row < 0 or row >= self.inspection_detail_table.rowCount():
            return
        self.inspection_detail_table.setCurrentCell(row, 0)
        self.refresh_criteria_results_panel(row)
        self.rebuild_criteria_groups(row)

    def on_detail_subtab_changed(self, index):
        if index == 1:
            row = self.inspection_detail_table.currentRow()
            self.refresh_criteria_results_panel(row)
            self.rebuild_criteria_groups(row)

    def refresh_criterion_summary_cell(self, row):
        table = getattr(self, "inspection_detail_table", None)
        if table is None or row < 0 or row >= table.rowCount():
            return
        item = table.item(row, 13)
        if item is None:
            item = QTableWidgetItem("")
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(row, 13, item)
        item.setText(self.criterion_summary_text(row))
        self.refresh_criteria_group_headers()

    def show_current_criteria_results_tab(self):
        row = self.inspection_detail_table.currentRow()
        self.refresh_criteria_results_panel(row)
        self.rebuild_criteria_groups(row)
        self.detail_subtabs.setCurrentIndex(1)

    def refresh_technical_opinion_candidates(self, current_row=None, *_args):
        if not hasattr(self, "technical_opinion_candidate_combo"):
            return
        row = (
            current_row
            if isinstance(current_row, int)
            else self.inspection_detail_table.currentRow()
        )
        candidates = self.technical_opinion_candidates(row)
        self.technical_opinion_candidate_combo.blockSignals(True)
        try:
            self.technical_opinion_candidate_combo.clear()
            self.technical_opinion_candidate_combo.addItem(
                "기술적소견 후보를 선택하십시오.", ""
            )
            for candidate in candidates:
                label = candidate["label"]
                text = candidate["text"]
                preview = text if len(text) <= 80 else text[:77] + "..."
                self.technical_opinion_candidate_combo.addItem(
                    f"[{label}] {preview}", text
                )
                index = self.technical_opinion_candidate_combo.count() - 1
                self.technical_opinion_candidate_combo.setItemData(
                    index, text, Qt.ToolTipRole
                )
        finally:
            self.technical_opinion_candidate_combo.blockSignals(False)
        enabled = row >= 0 and bool(candidates)
        self.technical_opinion_candidate_combo.setEnabled(enabled)
        self.technical_opinion_apply_button.setEnabled(enabled)

    def on_technical_opinion_item_changed(self, item):
        if item is not None and item.column() == 11:
            if item.row() == self.inspection_detail_table.currentRow():
                self.refresh_technical_opinion_candidates(item.row())

    def apply_selected_technical_opinion(self):
        row = self.inspection_detail_table.currentRow()
        if row < 0:
            return False
        selected = str(
            self.technical_opinion_candidate_combo.currentData() or ""
        ).strip()
        if not selected:
            return False
        opinion_item = self.inspection_detail_table.item(row, 11)
        if opinion_item is None:
            opinion_item = QTableWidgetItem("")
            self.inspection_detail_table.setItem(row, 11, opinion_item)
        current = opinion_item.text().strip()
        if current == selected:
            return False
        if current:
            answer = QMessageBox.question(
                self,
                "기술적소견 변경",
                "현재 기술적소견을 선택한 문구로 변경하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return False
        self.set_item_level_opinion(row, selected)
        self.refresh_technical_opinion_candidates(row)
        self.status_label.setText(
            "선택한 점검소견을 현재 점검항목에 적용했습니다. "
            "메인 사유·기술적소견에도 즉시 반영했습니다."
        )
        return True

    def on_inspection_detail_double_clicked(self, row, column):
        if column == 13:
            self.inspection_detail_table.setCurrentCell(row, 0)
            self.show_current_criteria_results_tab()

    def refresh_criteria_results_panel(self, current_row=None, *_args):
        if not hasattr(self, "criteria_results_panel"):
            return

        self.store_current_criteria_results()
        row = (
            current_row
            if isinstance(current_row, int)
            else self.inspection_detail_table.currentRow()
        )
        criteria = self.criteria_for_detail_row(row)
        self._criteria_panel_row = row
        self._clear_criteria_results_panel()

        if not criteria:
            self.criteria_results_panel.setVisible(False)
            self.refresh_criterion_summary_cell(row)
            return

        self.detail_subtabs.setTabEnabled(1, True)

        values = normalize_criteria_results(
            criteria,
            self._criteria_results_by_row.get(row, []),
            self.table_item_text(self.inspection_detail_table, row, 10),
        )
        self._criteria_results_by_row[row] = values
        self._loading_criteria_panel = True
        try:
            for index, (criterion, value) in enumerate(
                zip(criteria, values)
            ):
                card = QGroupBox(
                    f"{index + 1}. {criterion.get('name', '')}"
                )
                card_layout = QVBoxLayout(card)

                methods_layout = QHBoxLayout()
                methods_layout.addWidget(QLabel("수행방법"))
                method_checks = {}
                method_groups = {}
                original_methods = list(value.get("performed_methods", []))
                for method, label, legacy_methods in self._criterion_method_groups:
                    checkbox = QCheckBox(label)
                    checkbox.setChecked(
                        any(item in original_methods for item in legacy_methods)
                    )
                    checkbox.toggled.connect(
                        self._mark_criteria_results_changed
                    )
                    method_groups[method] = checkbox
                    for legacy_method in legacy_methods:
                        method_checks[legacy_method] = checkbox
                    methods_layout.addWidget(checkbox)
                methods_layout.addStretch()
                card_layout.addLayout(methods_layout)

                status_layout = QHBoxLayout()
                status_layout.addWidget(QLabel("수행상태"))
                status_combo = QComboBox()
                for status in INSPECTION_STATUS_OPTIONS:
                    status_combo.addItem(
                        self._criterion_status_labels[status], status
                    )
                status_index = status_combo.findData(
                    value.get("inspection_status", "not_checked")
                )
                status_combo.setCurrentIndex(max(status_index, 0))
                status_layout.addWidget(status_combo)

                status_layout.addWidget(QLabel("criterion 판정"))
                judgment_combo = QComboBox()
                for judgment in CRITERION_JUDGMENT_OPTIONS:
                    judgment_combo.addItem(
                        self._criterion_judgment_labels[judgment],
                        judgment,
                    )
                judgment_index = judgment_combo.findData(
                    value.get("criterion_judgment", "unset")
                )
                judgment_combo.setCurrentIndex(max(judgment_index, 0))
                status_layout.addWidget(judgment_combo)

                reason_label = QLabel("확인불가 사유")
                reason_combo = QComboBox()
                reason_combo.addItem("선택", "")
                for reason in UNAVAILABLE_REASON_OPTIONS:
                    reason_combo.addItem(
                        self._criterion_reason_labels[reason], reason
                    )
                reason_index = reason_combo.findData(
                    value.get("unavailable_reason", "")
                )
                reason_combo.setCurrentIndex(max(reason_index, 0))
                status_layout.addWidget(reason_label)
                status_layout.addWidget(reason_combo)
                status_layout.addStretch()
                card_layout.addLayout(status_layout)

                substitution = value.get("substitution", {})
                if substitution.get("used"):
                    legacy_note = QLabel(
                        "과거 대체확인 기록이 보존되어 있습니다. "
                        "신규 입력에서는 위 수행방법과 항목 단위 점검소견을 사용하십시오."
                    )
                    legacy_note.setStyleSheet(
                        "padding: 4px; color: #6b7280; background: #f7f7f7;"
                    )
                    legacy_note.setWordWrap(True)
                    card_layout.addWidget(legacy_note)

                editor = {
                    "methods": method_checks,
                    "method_groups": method_groups,
                    "original_methods": original_methods,
                    "status": status_combo,
                    "judgment": judgment_combo,
                    "reason_label": reason_label,
                    "reason": reason_combo,
                    "original_substitution": dict(substitution),
                    "original_evidence_note": value.get("evidence_note", ""),
                }
                status_combo.currentIndexChanged.connect(
                    lambda _index, e=editor: self._criterion_editor_changed(e)
                )
                reason_combo.currentIndexChanged.connect(
                    self._mark_criteria_results_changed
                )
                judgment_combo.currentIndexChanged.connect(
                    self._mark_criteria_results_changed
                )
                self._criterion_result_editors.append(editor)
                self._update_criterion_editor_visibility(editor)
                self.criteria_results_layout.addWidget(card)
            self.criteria_results_layout.addStretch()
        finally:
            self._loading_criteria_panel = False
        opinion_item = self.inspection_detail_table.item(row, 11)
        opinion = opinion_item.text() if opinion_item is not None else ""
        self._loading_criteria_item_opinion = True
        try:
            self.criteria_item_opinion.setPlainText(opinion)
        finally:
            self._loading_criteria_item_opinion = False
        self.refresh_criteria_completion_summary()
        self.refresh_technical_opinion_candidates(row)
        self.criteria_results_panel.setVisible(True)

    def load_equipment_inspection_detail(self, key, equipment_type):
        if hasattr(self, "detail_subtabs"):
            self.detail_subtabs.setCurrentIndex(0)
        items = self._inspection_db.get(equipment_type, [])
        saved = self.inspection_results.get(key, [])

        self._current_detail_inspection_items = items
        self._criteria_results_by_row = {}
        self._criteria_results_should_save = set()
        self._criteria_auto_opinion_by_row = {}
        self._criteria_panel_row = -1
        for row, item_data in enumerate(items):
            saved_row = saved[row] if row < len(saved) else {}
            criteria = measurement_metadata_for(item_data).get(
                "criteria", []
            )
            if not criteria:
                continue
            existing = saved_row.get("criteria_results")
            self._criteria_results_by_row[row] = normalize_criteria_results(
                criteria,
                existing,
                saved_row.get("판정", ""),
            )
            if isinstance(existing, list):
                self._criteria_results_should_save.add(row)

        self.inspection_detail_table.blockSignals(True)
        try:
            self.inspection_detail_table.setRowCount(len(items))

            for row, item_data in enumerate(items):
                saved_row = saved[row] if row < len(saved) else {}
                measurement_required = self.is_measurement_item(item_data)

                fixed_values = [
                    str(item_data["no"]),
                    item_data["name"],
                    item_data["method"],
                    item_data["criteria"],
                    "측정" if measurement_required else "확인",
                ]

                for column, value in enumerate(fixed_values):
                    table_item = QTableWidgetItem(value)
                    table_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    table_item.setTextAlignment(
                        Qt.AlignCenter if column in (0, 4) else Qt.AlignLeft
                    )
                    table_item.setToolTip(value)
                    self.inspection_detail_table.setItem(
                        row, column, table_item
                    )

                design_item = QTableWidgetItem(
                    saved_row.get("설계정격값", "")
                )
                measured_item = QTableWidgetItem(
                    saved_row.get("측정확인값", "")
                )
                unit_item = QTableWidgetItem(
                    saved_row.get("단위", "")
                )
                tolerance_item = QTableWidgetItem(
                    saved_row.get("허용편차", "")
                )
                deviation_item = QTableWidgetItem(
                    saved_row.get("편차율", "")
                )
                deviation_item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable
                )

                if not measurement_required:
                    design_item.setText("입력 불필요")
                    design_item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                    design_item.setTextAlignment(Qt.AlignCenter)

                    unit_item.setText("-")
                    tolerance_item.setText("-")
                    deviation_item.setText("-")

                    unit_item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                    tolerance_item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )

                self.inspection_detail_table.setItem(row, 5, design_item)
                self.inspection_detail_table.setItem(row, 6, measured_item)
                self.inspection_detail_table.setItem(row, 7, unit_item)
                self.inspection_detail_table.setItem(row, 8, tolerance_item)
                self.inspection_detail_table.setItem(row, 9, deviation_item)

                result_combo = QComboBox()
                result_combo.addItems(self._final_judgment_options)

                normalized_judgment = self.normalize_final_judgment(
                    saved_row.get("판정", "미점검")
                )
                result_index = result_combo.findText(
                    normalized_judgment
                )
                if result_index >= 0:
                    result_combo.setCurrentIndex(result_index)

                result_combo.currentTextChanged.connect(
                    lambda text, r=row: self.on_final_judgment_changed(
                        r, text
                    )
                )
                result_combo.currentTextChanged.connect(
                    lambda _text, r=row: (
                        self.refresh_criteria_completion_summary()
                        if r == self._criteria_panel_row
                        else None
                    )
                )
                result_combo.currentTextChanged.connect(
                    lambda _text, r=row: self.refresh_criteria_group_headers()
                )

                self.inspection_detail_table.setCellWidget(
                    row, 10, result_combo
                )
                opinion_item = QTableWidgetItem(
                    saved_row.get("기술적소견", "")
                )
                opinion_item.setToolTip(
                    saved_row.get("기술적소견", "")
                )
                self.inspection_detail_table.setItem(
                    row,
                    11,
                    opinion_item,
                )
                applicability_item = QTableWidgetItem("")
                applicability_item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable
                )
                applicability_item.setTextAlignment(Qt.AlignCenter)
                saved_review = saved_row.get("적용성확인")
                applicability_item.setData(
                    Qt.UserRole + 2,
                    dict(saved_review)
                    if isinstance(saved_review, dict)
                    else None,
                )
                self.inspection_detail_table.setItem(
                    row, 12, applicability_item
                )
                summary_item = QTableWidgetItem(
                    self.criterion_summary_text(row)
                )
                summary_item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable
                )
                summary_item.setTextAlignment(Qt.AlignCenter)
                self.inspection_detail_table.setItem(
                    row, 13, summary_item
                )

                if normalized_judgment == "X 불합격":
                    if not opinion_item.text().strip():
                        opinion_item.setText(
                            "[불합격 사유 입력 필요] 측정값·기준·이상상태·영향을 구체적으로 작성하십시오."
                        )
                    opinion_item.setBackground(QColor("#ffe2e2"))
        finally:
            self.inspection_detail_table.blockSignals(False)

        for row in range(self.inspection_detail_table.rowCount()):
            self.update_row_source_of_truth_edit_policy(row)

        self.refresh_inspection_applicability()
        if self.inspection_detail_table.rowCount() > 0:
            self.inspection_detail_table.setCurrentCell(0, 0)
        self.refresh_criteria_results_panel()
        self.rebuild_criteria_groups(
            self.inspection_detail_table.currentRow()
        )

    def refresh_inspection_applicability(self):
        """Refresh display-only applicability for the current chiller."""
        table = getattr(self, "inspection_detail_table", None)
        if table is None:
            return

        key = getattr(self, "current_detail_equipment_key", None)
        target_data = self.find_target_data_by_key(key) if key else None
        equipment_type = (
            target_data.get("설비종류", "") if target_data else ""
        )
        subtype = (
            target_data.get("세부유형", "unspecified")
            if target_data
            else "unspecified"
        )

        table.blockSignals(True)
        try:
            for row in range(table.rowCount()):
                display_item = table.item(row, 12)
                if display_item is None:
                    display_item = QTableWidgetItem("")
                    display_item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                    display_item.setTextAlignment(Qt.AlignCenter)
                    table.setItem(row, 12, display_item)

                if equipment_type != "냉동기":
                    display_item.setText("")
                    display_item.setToolTip("")
                    display_item.setData(Qt.UserRole, None)
                    display_item.setData(Qt.UserRole + 1, None)
                    continue

                item_no = self.table_item_text(table, row, 0)
                result = evaluate_chiller_item_applicability(
                    item_no, subtype
                )
                display_item.setData(Qt.UserRole, result["status"])
                display_item.setData(Qt.UserRole + 1, result["reason"])

                review = display_item.data(Qt.UserRole + 2)
                review_status = (
                    review.get("상태", "")
                    if isinstance(review, dict)
                    else ""
                )
                effective = resolve_effective_applicability(
                    result["status"], review, subtype
                )
                display_item.setText(effective["label"])
                display_item.setData(Qt.UserRole + 3, effective["status"])

                base_label = {
                    "applicable": "적용",
                    "not_applicable": "비적용",
                    "needs_confirmation": "확인필요",
                }[result["status"]]
                review_label = {
                    "confirmed_applicable": "적용확인",
                    "confirmed_not_applicable": "비적용확인",
                    "unresolved": "확인 계속 필요",
                }.get(review_status, "")
                current_code = normalize_chiller_subtype(subtype)
                tooltip_lines = [
                    f"기본 적용성: {base_label}",
                    f"기본 판단 이유: {result['reason']}",
                ]
                if review_label:
                    tooltip_lines.append(
                        f"사용자 확인결과: {review_label}"
                    )
                    note = str(review.get("메모", "")).strip()
                    if note:
                        tooltip_lines.append(f"확인메모: {note}")
                    confirmer = review.get("확인자", {})
                    if isinstance(confirmer, dict):
                        display_name = str(
                            confirmer.get("사용자명", "")
                        ).strip()
                        user_id = str(confirmer.get("아이디", "")).strip()
                        confirmer_text = display_name or user_id
                        if display_name and user_id:
                            confirmer_text += f" ({user_id})"
                        if confirmer_text:
                            tooltip_lines.append(
                                f"확인자: {confirmer_text}"
                            )
                    confirmed_at = str(
                        review.get("확인일시", "")
                    ).strip()
                    if confirmed_at:
                        tooltip_lines.append(
                            f"확인일시: {confirmed_at}"
                        )
                    reviewed_code = normalize_chiller_subtype(
                        review.get(
                            "확인당시세부유형", "unspecified"
                        )
                    )
                    tooltip_lines.append(
                        "확인 당시 subtype: "
                        + chiller_subtype_info(reviewed_code)["label"]
                        + f" ({reviewed_code})"
                    )
                tooltip_lines.append(
                    "현재 subtype: "
                    + chiller_subtype_info(current_code)["label"]
                    + f" ({current_code})"
                )
                tooltip_lines.append(
                    "재확인 필요 여부: "
                    + ("예" if effective["needs_recheck"] else "아니오")
                )
                tooltip_lines.append(
                    f"실무상태 판단: {effective['reason']}"
                )
                display_item.setToolTip("\n".join(tooltip_lines))

                judgment_combo = table.cellWidget(row, 10)
                judgment = self.normalize_final_judgment(
                    judgment_combo.currentText()
                    if judgment_combo
                    else "미점검"
                )
                warning = (
                    result["status"] != "not_applicable"
                    and judgment == "/ 해당없음"
                )
                if warning:
                    display_item.setText(
                        display_item.text() + " · 판정 재확인"
                    )
                    display_item.setToolTip(
                        display_item.toolTip()
                        + "\n현재 세부유형에서는 해당없음 판정을 재확인해야 합니다."
                    )
        finally:
            table.blockSignals(False)

        self.update_not_applicable_confirm_button()
        self.refresh_applicability_review_panel()

    def update_not_applicable_confirm_button(self, *_args):
        button = getattr(self, "confirm_not_applicable_button", None)
        table = getattr(self, "inspection_detail_table", None)
        if button is None or table is None:
            return

        row = table.currentRow()
        item = table.item(row, 12) if row >= 0 else None
        button.setEnabled(
            bool(item and item.data(Qt.UserRole) == "not_applicable")
        )

    def refresh_applicability_review_panel(self, *_args):
        if not hasattr(self, "applicability_review_result"):
            return

        table = self.inspection_detail_table
        row = table.currentRow()
        item = table.item(row, 12) if row >= 0 else None
        base_status = item.data(Qt.UserRole) if item else None
        enabled = base_status == "needs_confirmation"
        item_name = self.table_item_text(table, row, 1) if row >= 0 else ""
        item_no = self.table_item_text(table, row, 0) if row >= 0 else ""
        target_data = self.find_target_data_by_key(
            getattr(self, "current_detail_equipment_key", None)
        ) or {}
        subtype = normalize_chiller_subtype(
            target_data.get("세부유형", "unspecified")
        )
        review = item.data(Qt.UserRole + 2) if item else None
        review = review if isinstance(review, dict) else {}

        if enabled:
            guidance = chiller_confirmation_guidance(item_no, subtype)
            self.applicability_review_title.setText(
                f"[확인필요 상세] {item_name}"
            )
            self.applicability_review_guide.setText(
                "확인사항:\n" + "\n".join(f"• {text}" for text in guidance)
            )
        elif review:
            self.applicability_review_title.setText(
                f"[적용성 확인결과] {item_name}"
            )
            self.applicability_review_guide.setText(
                "현재 기본 적용성은 확인필요 상태가 아닙니다. "
                "기존 확인결과는 유지되며 세부유형 변경 여부를 재검토하십시오."
            )
        else:
            self.applicability_review_title.setText("[확인필요 상세]")
            self.applicability_review_guide.setText(
                "확인필요 상태인 냉동기 점검항목을 선택하십시오."
            )

        status = review.get("상태", "")
        index = self.applicability_review_result.findData(status)
        self.applicability_review_result.setCurrentIndex(max(index, 0))
        self.applicability_review_note.setText(review.get("메모", ""))
        self.applicability_review_result.setEnabled(enabled)
        self.applicability_review_note.setEnabled(enabled)
        self.applicability_review_save_button.setEnabled(enabled)

    def save_applicability_review(self):
        table = self.inspection_detail_table
        row = table.currentRow()
        item = table.item(row, 12) if row >= 0 else None
        if item is None or item.data(Qt.UserRole) != "needs_confirmation":
            return False

        status = self.applicability_review_result.currentData()
        if status not in {
            "confirmed_applicable",
            "confirmed_not_applicable",
            "unresolved",
        }:
            QMessageBox.warning(
                self, "적용성 확인", "확인결과를 선택하십시오."
            )
            return False

        target_data = self.find_target_data_by_key(
            self.current_detail_equipment_key
        ) or {}
        subtype = normalize_chiller_subtype(
            target_data.get("세부유형", "unspecified")
        )
        note = self.applicability_review_note.text().strip()
        previous = item.data(Qt.UserRole + 2)
        previous = previous if isinstance(previous, dict) else {}
        current_user = getattr(self, "current_user", {}) or {}
        review = {
            "상태": status,
            "메모": note,
            "확인일시": datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
            "확인자": {
                "아이디": current_user.get("id", ""),
                "사용자명": current_user.get("display_name", ""),
            },
            "확인당시세부유형": subtype,
            "기본적용성": item.data(Qt.UserRole),
        }
        item.setData(Qt.UserRole + 2, review)
        item_name = self.table_item_text(table, row, 1)
        self.write_audit(
            "inspection_applicability_reviewed",
            target=(
                f"냉동기 / {target_data.get('관리번호', '') or '관리번호 미지정'}"
                f" / {item_name}"
            ),
            field="적용성확인",
            before=previous.get("상태", ""),
            after=status,
            detail=(
                f"설비=냉동기 | 관리번호={target_data.get('관리번호', '')} | "
                f"세부유형={subtype} | 기본적용성={item.data(Qt.UserRole)} | "
                f"확인결과={status} | 확인메모={note}"
            ),
        )
        self.save_current_inspection_detail()
        self.refresh_inspection_applicability()
        return True

    def confirm_current_not_applicable(self):
        table = self.inspection_detail_table
        row = table.currentRow()
        applicability_item = table.item(row, 12) if row >= 0 else None
        if (
            applicability_item is None
            or applicability_item.data(Qt.UserRole) != "not_applicable"
        ):
            return False

        item_name = self.table_item_text(table, row, 1)
        reason = str(applicability_item.data(Qt.UserRole + 1) or "")
        answer = QMessageBox.question(
            self,
            "비적용 항목 확인",
            "이 항목은 현재 냉동기 세부유형 기준으로\n"
            "비적용 항목으로 판단되었습니다.\n\n"
            f"점검항목: {item_name}\n\n"
            f"판단사유: {reason}\n\n"
            "최종판정을 '/ 해당없음'으로 변경하시겠습니까?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False

        judgment_combo = table.cellWidget(row, 10)
        if judgment_combo is None:
            return False

        before = self.normalize_final_judgment(
            judgment_combo.currentText()
        )
        judgment_combo.setCurrentText("/ 해당없음")

        target_data = self.find_target_data_by_key(
            self.current_detail_equipment_key
        ) or {}
        subtype = normalize_chiller_subtype(
            target_data.get("세부유형", "unspecified")
        )
        subtype_label = chiller_subtype_info(subtype)["label"]
        self.write_audit(
            "inspection_not_applicable_confirmed",
            target=(
                f"냉동기 / {target_data.get('관리번호', '') or '관리번호 미지정'}"
                f" / {item_name}"
            ),
            field="최종판정",
            before=before,
            after="/ 해당없음",
            detail=(
                f"설비=냉동기 | 관리번호={target_data.get('관리번호', '')} | "
                f"세부유형={subtype}({subtype_label}) | "
                f"applicability_reason={reason}"
            ),
        )
        self.refresh_inspection_applicability()
        return True

    def save_current_inspection_detail(self):
        key = self.current_detail_equipment_key

        if not key or self.inspection_detail_table.rowCount() == 0:
            return

        self.store_current_criteria_results()

        target_data = self.find_target_data_by_key(key) or {}
        previous_rows = self.inspection_results.get(key, [])
        if not target_data and previous_rows:
            self.status_label.setText(
                "현재 점검대상과 연결되지 않은 기존 점검결과는 자동 변경하지 않았습니다."
            )
            return
        equipment_id = str(
            target_data.get("equipment_id", "") or ""
        ).strip()
        previous_equipment_id = self.equipment_id_for_inspection_record(
            previous_rows
        )
        if (
            previous_equipment_id
            and equipment_id
            and previous_equipment_id != equipment_id
            and self.register_row_for_equipment_id(previous_equipment_id) >= 0
        ):
            self.status_label.setText(
                "기존 점검결과의 장비 ID와 현재 점검대상이 달라 자동 이전하지 않았습니다."
            )
            return

        result_rows = []

        for row in range(self.inspection_detail_table.rowCount()):
            result_widget = self.inspection_detail_table.cellWidget(
                row, 10
            )
            input_type = self.table_item_text(
                self.inspection_detail_table, row, 4
            )

            result_rows.append(
                {
                    "번호": self.table_item_text(
                        self.inspection_detail_table, row, 0
                    ),
                    "점검내용": self.table_item_text(
                        self.inspection_detail_table, row, 1
                    ),
                    "점검방법": self.table_item_text(
                        self.inspection_detail_table, row, 2
                    ),
                    "점검기준": self.table_item_text(
                        self.inspection_detail_table, row, 3
                    ),
                    "입력구분": input_type,
                    "설계정격값": (
                        self.table_item_text(
                            self.inspection_detail_table, row, 5
                        )
                        if input_type == "측정"
                        else ""
                    ),
                    "측정확인값": self.table_item_text(
                        self.inspection_detail_table, row, 6
                    ),
                    "단위": (
                        self.table_item_text(
                            self.inspection_detail_table, row, 7
                        )
                        if input_type == "측정"
                        else ""
                    ),
                    "허용편차": (
                        self.table_item_text(
                            self.inspection_detail_table, row, 8
                        )
                        if input_type == "측정"
                        else ""
                    ),
                    "편차율": (
                        self.table_item_text(
                            self.inspection_detail_table, row, 9
                        )
                        if input_type == "측정"
                        else ""
                    ),
                    "판정": self.normalize_final_judgment(
                        result_widget.currentText()
                        if result_widget
                        else "미점검"
                    ),
                    "기술적소견": self.table_item_text(
                        self.inspection_detail_table, row, 11
                    ),
                }
            )
            applicability_item = self.inspection_detail_table.item(row, 12)
            review = (
                applicability_item.data(Qt.UserRole + 2)
                if applicability_item
                else None
            )
            if (
                isinstance(review, dict)
                and review.get("상태")
                in {
                    "confirmed_applicable",
                    "confirmed_not_applicable",
                    "unresolved",
                }
            ):
                result_rows[-1]["적용성확인"] = dict(review)

            if equipment_id:
                result_rows[-1]["equipment_id"] = equipment_id

            criteria = self.criteria_for_detail_row(row)
            if criteria and row in self._criteria_results_should_save:
                result_rows[-1]["criteria_results"] = (
                    normalize_criteria_results(
                        criteria,
                        self._criteria_results_by_row.get(row, []),
                        result_rows[-1].get("판정", ""),
                    )
                )

        previous_by_no = {
            str(item.get("번호", "")): item
            for item in previous_rows
            if isinstance(item, dict)
        }

        audit_fields = {
            "설계정격값": "설계·정격값",
            "측정확인값": "측정·확인값",
            "허용편차": "허용편차",
            "판정": "최종판정",
            "기술적소견": "기술적소견",
        }

        for new_item in result_rows:
            item_no = str(
                new_item.get("번호", "")
            )
            old_item = previous_by_no.get(
                item_no,
                {},
            )

            # 첫 저장은 모든 빈값을 변경이력으로 남기지 않고
            # 실제 입력값/판정이 생긴 필드만 기록
            for field_key, field_label in audit_fields.items():
                before = str(
                    old_item.get(field_key, "")
                )
                after = str(
                    new_item.get(field_key, "")
                )

                if before == after:
                    continue

                if (
                    not old_item
                    and not after.strip()
                ):
                    continue

                target_text = (
                    f"{key} / {new_item.get('점검내용','')}"
                )

                self.write_audit(
                    "점검결과 변경",
                    target=target_text,
                    field=field_label,
                    before=before,
                    after=after,
                )

        self.inspection_results[key] = result_rows
        self.refresh_target_status_only()
        self.status_label.setText(
            "현재 장비의 점검내용을 저장했습니다."
        )


    def refresh_target_status_only(self):
        for row in range(self.target_table.rowCount()):
            key = self.target_key_from_row(row)
            self.target_table.item(row, 6).setText(
                "점검내용 입력완료"
                if key in self.inspection_results
                else "점검내용 미입력"
            )

    def set_all_items_suitable(self):
        self.inspection_detail_table.blockSignals(True)
        try:
            for row in range(self.inspection_detail_table.rowCount()):
                result_widget = self.inspection_detail_table.cellWidget(
                    row, 10
                )
                if result_widget:
                    result_widget.setCurrentText("○ 합격")

                input_type = self.table_item_text(
                    self.inspection_detail_table, row, 4
                )
                measured_item = self.inspection_detail_table.item(
                    row, 6
                )

                if (
                    input_type == "확인"
                    and measured_item
                    and not measured_item.text().strip()
                ):
                    measured_item.setText("이상 없음")

                opinion_item = self.inspection_detail_table.item(
                    row, 11
                )
                if opinion_item is None:
                    opinion_item = QTableWidgetItem("")
                    self.inspection_detail_table.setItem(
                        row, 11, opinion_item
                    )

                if not opinion_item.text().strip():
                    opinion_item.setText(
                        self.default_pass_reason(row)
                    )
                opinion_item.setBackground(QColor("white"))

        finally:
            self.inspection_detail_table.blockSignals(False)

        self.save_current_inspection_detail()
        self.refresh_technical_opinion_candidates(
            self.inspection_detail_table.currentRow()
        )
        self.status_label.setText(
            "현재 장비의 직접 판정 항목을 ○ 합격으로 입력했습니다. "
            "저장된 criterion 수행결과가 있는 항목은 종합판정을 유지합니다."
        )
