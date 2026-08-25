import os
import logging
import shutil
import xml.etree.ElementTree as ET
import sys
from pathlib import Path
from PySide6.QtCore import QDate, QSettings, Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from catalogs import (
    DESIGN_MEASURE_REVIEW_KEYWORDS,
    EQUIPMENT_LIST,
    FINAL_JUDGMENT_OPTIONS,
    GUIDELINE_DOCUMENTS,
    INSPECTION_DB,
    LIFESPAN_BY_EQUIPMENT,
    LIFESPAN_SOURCE_OPTIONS,
    OPERATION_REVIEW_KEYWORDS,
    PERFORMANCE_CALC_DEFS,
    REPORT_CHECKLIST_ITEMS,
    STAFF_LIST,
    SYSTEM_REVIEW_FIXED_ROWS,
)







# 사용자가 제공한 보고서의 TOE 산정값과 일치하는 기본 환산계수





IMPROVEMENT_DEFAULTS = {
    "냉동기": ("매년 세관작업 및 열교환 성능 확인", ["보수"] * 5),
    "냉각탑": ("충진물·살수장치·송풍기 상태 점검", ["교체", "-", "-", "점검", "-"]),
    "보일러": ("연소공기비·배기가스 및 안전장치 재조정", ["개선", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "열교환기": ("매년 세관작업 및 열교환 효율 확인", ["보수"] * 5),
    "팽창탱크": ("봉입압력·블래더·안전밸브 점검", ["점검", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "펌프(냉난방·급수)": ("내부 마모·메커니컬씰·베어링 정기점검", ["점검", "보수", "유지관리", "유지관리", "유지관리"]),
    "패키지에어컨": ("필터관리·냉매량·실외기 고정상태 점검", ["개선", "점검", "-", "-", "-"]),
    "항온항습기": ("냉동시스템·가습기·제어상태 점검", ["점검", "보수", "유지관리", "유지관리", "유지관리"]),
    "공기조화기": ("송풍기·모터·댐퍼·코일 상태 점검", ["보수", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "팬코일유닛": ("필터청소·팬·전동밸브 점검", ["개선", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "환기설비": ("팬·모터·벨트·댐퍼·필터 관리", ["점검", "교체", "-", "-", "-"]),
    "필터": ("주기적인 청소 및 차압기준에 따른 교체", ["개선", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "위생기구설비": ("수전 작동·누수·수격현상 점검", ["점검", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "급수·급탕설비": ("배관단열·순환상태·안전밸브 점검", ["보수", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "고·저수조": ("내부상태·수위센서·수질관리 정기점검", ["점검", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "오·배수통기 및 우수배수설비": ("집수정·배수펌프·수위경보 관리", ["개선", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "배관설비": ("누수·부식·지지상태·신축이음 점검", ["점검", "보수", "유지관리", "유지관리", "유지관리"]),
    "덕트설비": ("덕트 연결·단열·결로·댐퍼 상태 점검", ["점검", "보수", "유지관리", "유지관리", "유지관리"]),
    "보온설비": ("결로·동파·열손실 및 보온재 손상 점검", ["개선", "유지관리", "유지관리", "유지관리", "유지관리"]),
    "자동제어설비": ("통신회선·전원·경보·기록기능 점검", ["점검", "점검", "보수", "유지관리", "유지관리"]),
    "방음·방진·내진설비": ("소음·진동·고정볼트·방진재 정기점검", ["점검", "유지관리", "유지관리", "유지관리", "유지관리"]),
}

PHOTO_REQUIREMENTS_BY_EQUIPMENT = {
    "냉동기": [
        "장비 전체사진",
        "명판사진",
        "제어반 운전상태",
        "증발기·응축기 압력",
        "냉수·냉각수 입출구 온도",
    ],
    "냉각탑": [
        "장비 전체사진",
        "명판사진",
        "수조·볼탭",
        "살수노즐·충진재",
        "송풍기·모터",
    ],
    "보일러": [
        "장비 전체사진",
        "명판사진",
        "연소상태",
        "운전압력·수위",
        "안전밸브",
        "배기가스 측정",
    ],
    "열교환기": [
        "장비 전체사진",
        "명판사진",
        "1·2차측 온도·압력",
        "안전밸브·증기트랩",
    ],
    "펌프(냉난방·급수)": [
        "장비 전체사진",
        "명판사진",
        "압력계·유량 측정",
        "전류 측정",
        "진동·소음 측정",
        "베이스·앵커볼트",
    ],
    "공기조화기": [
        "장비 전체사진",
        "명판사진",
        "필터·코일",
        "댐퍼 작동",
        "송풍기·벨트",
        "풍량 측정",
    ],
    "환기설비": [
        "장비 전체사진",
        "명판사진",
        "송풍기·벨트",
        "댐퍼 상태",
        "급·배기 풍량 측정",
    ],
    "필터": [
        "필터 전체사진",
        "필터 오염상태",
        "차압 측정",
    ],
    "고·저수조": [
        "수조 전체사진",
        "내부·외부 상태",
        "수위센서",
        "수질검사 성적서",
    ],
    "자동제어설비": [
        "중앙감시반 전체사진",
        "운전·경보 화면",
        "기록 조회 화면",
        "백신·방화벽 상태",
    ],
}

SURVEY_EQUIPMENT_ALIASES = {
    "냉동기": ["냉동기", "냉온수기"],
    "냉각탑": ["냉각탑"],
    "축열조": ["축열조"],
    "보일러": ["보일러"],
    "열교환기": ["열교환기"],
    "팽창탱크": ["팽창탱크"],
    "펌프(냉난방·급수)": ["냉난방펌프", "냉수펌프", "온수펌프", "급수펌프", "펌프"],
    "신재생에너지(태양열·지열)": ["신재생", "태양열", "지열"],
    "연료전지": ["연료전지"],
    "패키지에어컨": ["패키지에어컨", "패키지 에어컨", "패키지 에어콘", "EHP", "GHP"],
    "항온항습기": ["항온항습기", "항온 항습기"],
    "공기조화기": ["공기조화기", "공조기"],
    "팬코일유닛": ["팬코일유닛", "팬코일"],
    "환기설비": ["환기설비", "환기팬"],
    "필터": ["필터"],
    "위생기구설비": ["위생기구설비", "위생기구"],
    "급수·급탕설비": ["급수·급탕설비", "급수급탕설비", "급수,급탕설비", "급수펌프, 급탕탱크 등", "급수펌프", "급탕탱크"],
    "고·저수조": ["고·저수조", "고저수조", "저수조", "고가수조"],
    "오·배수통기 및 우수배수설비": [
        "오·배수통기 및 우수배수설비",
        "오,배수통기 및 우수배수 설비",
        "오배수통기",
        "우수배수설비",
        "배수설비",
    ],
    "오수정화설비": ["오수정화설비", "오수정화"],
    "물재이용설비": ["물재이용설비", "물 재이용설비", "중수도", "중수"],
    "배관설비": ["배관설비"],
    "덕트설비": ["덕트설비", "덕트"],
    "보온설비": ["보온설비", "보온"],
    "자동제어설비": ["자동제어설비", "자동제어"],
    "방음·방진·내진설비": ["방음·방진·내진설비", "방음방진내진설비", "방음", "방진", "내진"],
}

PHOTO_BASE_REQUIREMENTS = [
    "장비 전체사진",
    "명판사진",
]

PHOTO_REQUIREMENTS_BY_INSPECTION_ITEM = {
    "유지관리 점검표 확인": [
        "유지관리 점검표 보유·작성상태",
    ],
    "레지오넬라균(수질검사, 공중위생관리법 관련)": [
        "레지오넬라균 수질검사 성적서",
    ],
    "경보 상태": [
        "경보·이력 화면",
    ],
    "안전장치(인터록) 상태": [
        "안전장치·인터록 작동상태",
    ],
    "에너지 사용량": [
        "에너지 사용량 증빙자료",
    ],
}











COMPANY_NAME = "조광설비(주)"



APP_ORGANIZATION = "ChokwangEngineering"
APP_NAME = "MechanicalPerformanceInspection"

from auth import (
    AuditLogDialog,
    AuthManager,
    FirstAdminDialog,
    LoginDialog,
    UserManagementDialog,
)
from comparison import ComparisonManagerMixin, ComparisonServiceMixin
from energy import EnergyManagerMixin
from inspection import (
    InspectionServiceMixin,
    PerformanceCalculationMixin,
)
from photos import PhotoManagerMixin
from project import ProjectServiceMixin
from rca import RcaManagerMixin, RcaServiceMixin
from survey import SurveyManagerMixin, SurveyParserMixin, SurveyReaderMixin
from ui import (
    ChecklistPageMixin,
    EquipmentPageMixin,
    InspectionPageMixin,
    ImprovementPageMixin,
    SitePageMixin,
    SystemReviewPageMixin,
    TechnicianPageMixin,
)
from report import (
    HwpComUnavailableError,
    HwpSecurityModuleRegistrationError,
    ProductionHwpSaveError,
    ProductionPdfSaveError,
    ProductionPhotoFileMissingError,
    ProductionProjectDataError,
    ProductionSecurityModuleMissingError,
    generate_production_hwp,
    prepare_production_report,
    validate_production_document,
    verify_production_hwp_environment,
    HwpReportAdapter,
    MINIMAL_REPEAT_HWP_CONTRACT,
    build_report_document,
)
from report.phase3_test_runtime import (
    PHASE3_TEST_TEMPLATE_NAME,
    build_current_project_snapshot,
    create_minimal_repeat_template,
    phase3_output_path,
)


LOGGER = logging.getLogger(__name__)


def production_report_error_message(error):
    if isinstance(error, ProductionSecurityModuleMissingError):
        return (
            "한글 자동화 보안모듈이 설치되지 않았습니다.\n"
            f"{error}\n설치 상태를 확인하십시오."
        )
    if isinstance(error, HwpSecurityModuleRegistrationError):
        return (
            "한글 자동화 보안모듈을 등록하지 못했습니다.\n"
            "FilePathCheckerModuleExample 등록 상태를 확인하십시오."
        )
    if isinstance(error, HwpComUnavailableError):
        return "한글 프로그램에 연결하지 못했습니다. 한글 2024 설치 상태를 확인하십시오."
    if isinstance(error, ProductionProjectDataError):
        return f"정식 보고서에 필요한 프로젝트 데이터가 부족합니다.\n{error}"
    if isinstance(error, ProductionPhotoFileMissingError):
        return f"보고서에 연결된 사진 파일을 찾을 수 없습니다.\n{error}"
    if isinstance(error, ProductionHwpSaveError):
        return f"정식 HWP 저장에 실패했습니다.\n{error}"
    if isinstance(error, ProductionPdfSaveError):
        return f"PDF 비교본 변환에 실패했습니다.\n{error}"
    return (
        "정식 결과보고서 생성 중 오류가 발생했습니다.\n"
        "프로젝트 데이터를 확인한 뒤 다시 시도하십시오."
    )


class PerformanceInspectionApp(
    SurveyManagerMixin,
    SurveyParserMixin,
    SurveyReaderMixin,
    ChecklistPageMixin,
    ImprovementPageMixin,
    SystemReviewPageMixin,
    InspectionPageMixin,
    TechnicianPageMixin,
    EquipmentPageMixin,
    SitePageMixin,
    PhotoManagerMixin,
    EnergyManagerMixin,
    InspectionServiceMixin,
    PerformanceCalculationMixin,
    ProjectServiceMixin,
    RcaServiceMixin,
    RcaManagerMixin,
    ComparisonServiceMixin,
    ComparisonManagerMixin,
    QMainWindow,
):
    _equipment_list = EQUIPMENT_LIST
    _staff_list = STAFF_LIST
    _company_name = COMPANY_NAME
    _final_judgment_options = FINAL_JUDGMENT_OPTIONS
    _inspection_db = INSPECTION_DB
    _performance_calc_defs = PERFORMANCE_CALC_DEFS
    _design_measure_review_keywords = DESIGN_MEASURE_REVIEW_KEYWORDS
    _guideline_documents = GUIDELINE_DOCUMENTS
    _operation_review_keywords = OPERATION_REVIEW_KEYWORDS
    _system_review_fixed_rows = SYSTEM_REVIEW_FIXED_ROWS
    _improvement_defaults = IMPROVEMENT_DEFAULTS
    _lifespan_by_equipment = LIFESPAN_BY_EQUIPMENT
    _lifespan_source_options = LIFESPAN_SOURCE_OPTIONS
    _report_checklist_items = REPORT_CHECKLIST_ITEMS
    _survey_equipment_aliases = SURVEY_EQUIPMENT_ALIASES
    _photo_inspection_db = INSPECTION_DB
    _photo_base_requirements = PHOTO_BASE_REQUIREMENTS
    _photo_requirements_by_equipment = PHOTO_REQUIREMENTS_BY_EQUIPMENT
    _photo_requirements_by_inspection_item = (
        PHOTO_REQUIREMENTS_BY_INSPECTION_ITEM
    )
    def __init__(self, current_user=None, auth_manager=None):
        super().__init__()

        self.current_user = current_user or {
            "id": "local",
            "display_name": "사용자",
            "role": "user",
        }
        self.auth_manager = auth_manager

        self.setWindowTitle("기계설비 성능점검 시스템 v3.16.1.1 - 작업기록 수정")
        self.resize(1200, 820)
        self.current_file = None
        self.inspection_results = {}
        self.cause_analysis = []
        self.previous_project_data = {}
        self.previous_project_path = ""
        self.previous_compare_results = []
        self.performance_calculations = []
        self.current_detail_equipment_key = None
        self.target_selections = []
        self.photo_records = []
        self.current_photo_id = None
        self.last_photo_source_dir = str(Path.home())

        # 프로그램을 종료해도 최근 대상조사표 폴더를 기억
        self.settings = QSettings(
            APP_ORGANIZATION,
            APP_NAME,
        )
        saved_survey_dir = self.settings.value(
            "last_survey_directory",
            str(Path.home()),
            type=str,
        )
        self.last_survey_directory = (
            saved_survey_dir
            if saved_survey_dir
            and Path(saved_survey_dir).exists()
            else str(Path.home())
        )

        self.create_ui()

    def current_site_name_for_audit(self):
        try:
            return self.site_name.text().strip()
        except Exception:
            return ""

    def write_audit(
        self,
        action,
        target="",
        field="",
        before="",
        after="",
        detail="",
        site=None,
    ):
        if not self.auth_manager:
            return

        self.auth_manager.write_audit(
            self.current_user,
            action,
            site=(
                self.current_site_name_for_audit()
                if site is None
                else site
            ),
            target=target,
            field=field,
            before=before,
            after=after,
            detail=detail,
        )

    def open_audit_log(self):
        if not self.auth_manager:
            return

        dialog = AuditLogDialog(
            self.auth_manager,
            self.current_user,
            self,
        )
        dialog.exec()

    def open_user_management(self):
        if self.current_user.get("role") != "admin":
            QMessageBox.warning(
                self,
                "권한 없음",
                "관리자만 사용자 관리를 할 수 있습니다.",
            )
            return

        if not self.auth_manager:
            return

        dialog = UserManagementDialog(
            self.auth_manager,
            self.current_user,
            self,
        )
        dialog.exec()

    def logout(self):
        answer = QMessageBox.question(
            self,
            "로그아웃",
            "현재 프로그램을 종료하고 로그인 화면으로 돌아가시겠습니까?",
        )
        if answer != QMessageBox.Yes:
            return

        self.write_audit(
            "로그아웃",
            detail="사용자 요청",
        )
        QApplication.exit(1001)

    def create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)

        title = QLabel("기계설비 성능점검 시스템 v3.16.1")
        title.setStyleSheet(
            """
            QLabel {
                font-size: 25px;
                font-weight: bold;
                padding: 12px;
            }
            """
        )
        root_layout.addWidget(title)

        top_buttons = QHBoxLayout()

        self.new_button = QPushButton("신규 프로젝트")
        self.open_button = QPushButton("프로젝트 열기")
        self.save_button = QPushButton("프로젝트 저장")

        top_buttons.addWidget(self.new_button)
        top_buttons.addWidget(self.open_button)
        top_buttons.addWidget(self.save_button)
        top_buttons.addStretch()

        role_text = (
            "관리자"
            if self.current_user.get("role") == "admin"
            else "일반사용자"
        )
        self.logged_user_label = QLabel(
            f"사용자: {self.current_user.get('display_name', self.current_user.get('id',''))} "
            f"| {role_text}"
        )
        self.logged_user_label.setStyleSheet(
            "font-weight:bold; padding:6px;"
        )
        top_buttons.addWidget(self.logged_user_label)

        self.audit_log_button = QPushButton("작업기록")
        self.audit_log_button.clicked.connect(
            self.open_audit_log
        )
        top_buttons.addWidget(self.audit_log_button)

        self.user_manage_button = QPushButton("사용자 관리")
        self.user_manage_button.setVisible(
            self.current_user.get("role") == "admin"
        )
        self.user_manage_button.clicked.connect(
            self.open_user_management
        )
        top_buttons.addWidget(self.user_manage_button)

        self.logout_button = QPushButton("로그아웃")
        self.logout_button.clicked.connect(self.logout)
        top_buttons.addWidget(self.logout_button)

        root_layout.addLayout(top_buttons)

        body_layout = QHBoxLayout()

        self.menu = QListWidget()
        self.menu.setFixedWidth(210)
        self.menu.addItems(
            [
                "1. 현장정보",
                "2. 설비현황",
                "3. 성능점검 기술자",
                "4. 점검결과",
                "5. 사진관리",
                "6. 시스템 검토",
                "7. 노후도·개선계획",
                "8. 에너지 분석",
                "9. 자체검증",
                "10. 보고서 생성 (추후 개발)",
            ]
        )
        self.menu.setStyleSheet(
            """
            QListWidget {
                font-size: 15px;
                padding: 5px;
            }

            QListWidget::item {
                padding: 12px;
            }

            QListWidget::item:selected {
                background: #dbeafe;
                color: #111827;
                font-weight: bold;
            }
            """
        )

        body_layout.addWidget(self.menu)

        self.pages = QStackedWidget()

        self.site_page = self.create_site_page()
        self.equipment_page = self.create_equipment_page()
        self.technician_page = self.create_technician_page()
        self.inspection_page = self.create_inspection_page()
        self.photo_page = self.create_photo_page()
        self.system_review_page = self.create_system_review_page()
        self.improvement_page = self.create_improvement_page()
        self.energy_page = self.create_energy_page()
        self.checklist_page = self.create_checklist_page()
        self.report_page = self.create_report_page()

        self.pages.addWidget(self.site_page)
        self.pages.addWidget(self.equipment_page)
        self.pages.addWidget(self.technician_page)
        self.pages.addWidget(self.inspection_page)
        self.pages.addWidget(self.photo_page)
        self.pages.addWidget(self.system_review_page)
        self.pages.addWidget(self.improvement_page)
        self.pages.addWidget(self.energy_page)
        self.pages.addWidget(self.checklist_page)
        self.pages.addWidget(self.report_page)

        body_layout.addWidget(self.pages, 1)
        root_layout.addLayout(body_layout, 1)

        self.status_label = QLabel("현장정보를 입력하십시오.")
        self.status_label.setStyleSheet(
            """
            QLabel {
                padding: 10px;
                border: 1px solid #aaaaaa;
                background: #f5f5f5;
            }
            """
        )
        root_layout.addWidget(self.status_label)

        self.menu.currentRowChanged.connect(self.change_page)
        self.menu.setCurrentRow(0)

        self.new_button.clicked.connect(self.clear_all)
        self.open_button.clicked.connect(self.open_project)
        self.save_button.clicked.connect(self.save_project)
    def create_report_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("10. 보고서 생성")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        notice = QLabel(
            "공식 한컴 자동화 보안모듈을 사용하는 정식 결과보고서를 생성합니다. "
            "최종 산출물은 HWP이며 확인용 PDF를 함께 저장합니다. "
            "아래 Phase 1~3 테스트 보고서는 기존 검증 경로로 별도 유지됩니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding: 14px; background: #fff7d6; "
            "border: 1px solid #e6c65c; font-size: 14px;"
        )
        layout.addWidget(notice)

        detail = QLabel(
            "현재 프로그램에서는 1~9번의 현장정보, 설비현황, 기술자, 점검결과, "
            "사진, 시스템 검토, 노후도·개선계획, 에너지 분석, 자체검증 자료를 "
            "정확하게 축적하는 데 집중합니다."
        )
        detail.setWordWrap(True)
        detail.setStyleSheet(
            "padding: 10px; background: #eef6ff; border: 1px solid #9ec5e5;"
        )
        layout.addWidget(detail)


        production_notice = QLabel(
            "현재 프로젝트의 전체 점검대상, 사진, 시스템검토, 노후도와 "
            "개선계획을 반영하는 production 보고서입니다."
        )
        production_notice.setWordWrap(True)
        production_notice.setStyleSheet(
            "padding: 10px; background: #eef6ff; border: 1px solid #2c5f8a;"
        )
        layout.addWidget(production_notice)

        self.production_report_button = QPushButton("정식 결과보고서 생성")
        self.production_report_button.setMinimumHeight(48)
        self.production_report_button.clicked.connect(
            self.generate_production_report
        )
        layout.addWidget(self.production_report_button)

        self.production_report_status = QLabel("정식 결과보고서: 생성 전")
        self.production_report_status.setWordWrap(True)
        self.production_report_status.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        layout.addWidget(self.production_report_status)
        test_notice = QLabel(
            "Phase 1~3 검증 전용입니다. 현재 프로젝트를 읽기 전용 스냅샷으로 "
            "변환하여 최소 HWP 템플릿에 설비별 점검표를 반복 출력합니다. "
            "기존 정식 보고서 및 legacy 생성 경로는 사용하지 않습니다."
        )
        test_notice.setWordWrap(True)
        test_notice.setStyleSheet(
            "padding: 10px; background: #eefbf2; border: 1px solid #76b886;"
        )
        layout.addWidget(test_notice)

        self.phase3_test_report_button = QPushButton(
            "Phase 1~3 테스트 보고서 생성"
        )
        self.phase3_test_report_button.setMinimumHeight(44)
        self.phase3_test_report_button.clicked.connect(
            self.generate_phase3_test_report
        )
        layout.addWidget(self.phase3_test_report_button)

        self.phase3_test_report_path = QLabel("생성된 테스트 보고서: 없음")
        self.phase3_test_report_path.setWordWrap(True)
        self.phase3_test_report_path.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        layout.addWidget(self.phase3_test_report_path)

        self.phase3_open_report_button = QPushButton("생성된 HWP 바로 열기")
        self.phase3_open_report_button.setEnabled(False)
        self.phase3_open_report_button.clicked.connect(
            self.open_phase3_test_report
        )
        layout.addWidget(self.phase3_open_report_button)

        layout.addStretch()

        previous_button = QPushButton("이전: 자체검증")
        previous_button.setMinimumHeight(40)
        previous_button.clicked.connect(
            lambda: self.menu.setCurrentRow(8)
        )
        layout.addWidget(previous_button)

        return page

    def _set_production_report_status(self, text):
        self.production_report_status.setText(f"정식 결과보고서: {text}")
        self.status_label.setText(text)
        QApplication.processEvents()

    def generate_production_report(self):
        """Generate the customer production HWP through production_service."""
        self.save_current_inspection_detail()
        preflight_issues = self.collect_report_criterion_preflight_issues()
        if preflight_issues:
            action, issue = self.show_report_preflight_dialog(preflight_issues)
            if action == "move":
                self.move_to_report_preflight_issue(issue)
                return
            if action != "continue":
                return

        self.production_report_button.setEnabled(False)
        cursor_set = False
        try:
            self._set_production_report_status("보고서 데이터 준비 중")
            project_snapshot = build_current_project_snapshot(self)
            document = build_report_document(project_snapshot)
            validate_production_document(document)
            production_view = prepare_production_report(project_snapshot)

            output_directory = Path.cwd() / "generated_reports"
            output_directory.mkdir(parents=True, exist_ok=True)
            site_name = str(document.site.values.get("현장명", "")).strip() or "현장"
            default_name = self.safe_filename(
                f"{site_name}_기계설비성능점검_결과보고서.hwp"
            )
            selected_path, _ = QFileDialog.getSaveFileName(
                self,
                "정식 결과보고서 저장",
                str(output_directory / default_name),
                "한글 문서 (*.hwp)",
            )
            if not selected_path:
                self._set_production_report_status("사용자 취소")
                return

            output_path = Path(selected_path)
            if output_path.suffix.lower() != ".hwp":
                output_path = output_path.with_suffix(".hwp")
            pdf_path = output_path.with_suffix(".pdf")

            QApplication.setOverrideCursor(Qt.WaitCursor)
            cursor_set = True
            self._set_production_report_status("한글 자동화 보안모듈 확인 중")
            verify_production_hwp_environment()
            self._set_production_report_status("HWP 생성 중")
            result = generate_production_hwp(
                project_snapshot,
                output_path,
                pdf_preview_path=pdf_path,
                visible=False,
                progress_callback=self._set_production_report_status,
            )

            self._production_last_report_path = result.output_path
            warnings = list(dict.fromkeys(
                list(document.report_warnings)
                + list(production_view.warnings)
                + list(result.warnings)
            ))
            warning_text = ""
            if warnings:
                warning_text = "\n\n경고:\n- " + "\n- ".join(warnings)
            self._set_production_report_status("완료")
            self.production_report_status.setText(
                "정식 결과보고서 생성 완료\n"
                f"HWP: {result.output_path}\n"
                f"PDF: {result.pdf_preview_path}\n"
                f"총 {result.page_count}쪽"
            )
            QMessageBox.information(
                self,
                "정식 결과보고서 생성 완료",
                "정식 결과보고서 생성 완료\n\n"
                f"HWP:\n{result.output_path}\n\n"
                f"PDF:\n{result.pdf_preview_path}\n\n"
                f"총 {result.page_count}쪽"
                f"{warning_text}",
            )
        except Exception as error:
            LOGGER.exception("Production HWP generation failed")
            self._set_production_report_status("생성 실패")
            QMessageBox.critical(
                self,
                "정식 결과보고서 생성 실패",
                production_report_error_message(error),
            )
        finally:
            if cursor_set:
                QApplication.restoreOverrideCursor()
            self.production_report_button.setEnabled(True)

    def generate_phase3_test_report(self):
        """Run the isolated Phase 1-3 report path without saving project JSON."""
        self.save_current_inspection_detail()
        preflight_issues = self.collect_report_criterion_preflight_issues()
        if preflight_issues:
            action, issue = self.show_report_preflight_dialog(preflight_issues)
            if action == "move":
                self.move_to_report_preflight_issue(issue)
                return
            if action != "continue":
                return

        self.phase3_test_report_button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            project_snapshot = build_current_project_snapshot(self)
            document = build_report_document(project_snapshot)
            output_directory = Path.cwd() / "generated_reports" / "phase3_test"
            output_directory.mkdir(parents=True, exist_ok=True)
            template_path = (
                Path.cwd() / "templates" / PHASE3_TEST_TEMPLATE_NAME
            )
            if not template_path.is_file():
                create_minimal_repeat_template(template_path)
            output_path = phase3_output_path(
                output_directory,
                str(document.site.values.get("현장명", "")),
            )
            result = HwpReportAdapter().generate(
                document,
                MINIMAL_REPEAT_HWP_CONTRACT,
                template_path,
                output_path,
                visible=False,
            )
            self._phase3_last_report_path = result.output_path
            self.phase3_test_report_path.setText(
                f"생성된 테스트 보고서: {result.output_path}"
            )
            self.phase3_open_report_button.setEnabled(True)
            warning_text = ""
            if result.warnings or document.report_warnings:
                warning_text = "\n\n경고:\n- " + "\n- ".join(
                    list(document.report_warnings) + list(result.warnings)
                )
            QMessageBox.information(
                self,
                "Phase 1~3 테스트 보고서 생성 완료",
                "정식 보고서가 아닌 Phase 1~3 검증용 HWP를 생성했습니다.\n\n"
                f"대상 설비: {len(document.targets)}개\n"
                f"점검항목: {sum(len(item.inspection_items) for item in document.targets)}개\n"
                f"파일: {result.output_path}"
                f"{warning_text}",
            )
            self.status_label.setText(
                f"Phase 1~3 테스트 보고서 생성 완료: {result.output_path}"
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Phase 1~3 테스트 보고서 생성 실패",
                f"기존 프로젝트 파일은 변경되지 않았습니다.\n\n"
                f"{type(error).__name__}: {error}",
            )
        finally:
            QApplication.restoreOverrideCursor()
            self.phase3_test_report_button.setEnabled(True)

    def open_phase3_test_report(self):
        path = Path(getattr(self, "_phase3_last_report_path", ""))
        if not path.is_file():
            self.phase3_open_report_button.setEnabled(False)
            QMessageBox.warning(self, "파일 없음", "생성된 테스트 HWP를 찾을 수 없습니다.")
            return
        try:
            os.startfile(str(path))
        except OSError as error:
            QMessageBox.critical(self, "HWP 열기 실패", str(error))


    @staticmethod
    def create_date_edit():
        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat("yyyy-MM-dd")
        date_edit.setDate(QDate.currentDate())
        return date_edit

    def change_page(self, index):
        if index >= 0:
            self.pages.setCurrentIndex(index)

        if index == 4 and hasattr(self, "photo_equipment_combo"):
            self.populate_photo_equipment_combo()
            self.refresh_photo_table()

        if index == 5 and hasattr(self, "report_filename"):
            self.prepare_report_page()

    def go_to_site_page(self):
        self.menu.setCurrentRow(0)

    def go_to_equipment_page(self):
        site_data = self.collect_site_data()

        if not self.validate_site_data(site_data):
            return

        self.menu.setCurrentRow(1)
        self.status_label.setText(
            "현장정보 확인 완료. 설비현황을 입력하십시오."
        )

    def go_to_technician_page(self):
        if self.count_selected_equipment() == 0:
            QMessageBox.warning(
                self,
                "설비현황 확인",
                "점검대상 기계설비를 한 종류 이상 입력하십시오.",
            )
            return

        self.menu.setCurrentRow(2)
        self.status_label.setText(
            "설비현황 입력 완료. 참여기술자를 입력하십시오."
        )

    def go_to_inspection_page(self):
        if not self.validate_technicians():
            return

        self.menu.setCurrentRow(3)

        if self.equipment_register_table.rowCount() == 0:
            self.generate_equipment_register(confirm_replace=False)

        self.detail_technicians_label.setText(
            ", ".join(self.selected_technician_names())
        )
        self.status_label.setText(
            "성능점검 기술자 입력 완료. 장비대장과 설비별 점검내용을 입력하십시오."
        )

    def go_to_photo_page(self):
        self.save_current_inspection_detail()
        self.refresh_target_table()

        valid_rows = self.valid_photo_target_rows()

        if not valid_rows:
            QMessageBox.warning(
                self,
                "점검대상 확인",
                "사진과 연동할 점검대상이 없습니다.\n\n"
                "4-2 점검대상 선정에서 관리번호를 먼저 선택하십시오.",
            )
            self.menu.setCurrentRow(3)
            return

        self.menu.setCurrentRow(4)
        self.populate_photo_equipment_combo()
        self.refresh_photo_table()
        self.status_label.setText(
            f"점검대상 {len(valid_rows)}건과 사진관리 화면을 연동했습니다."
        )
        name_combo.setEditable(True)
    def collect_equipment_register_data(self):
        return [
            self.register_row_data(row)
            for row in range(
                self.equipment_register_table.rowCount()
            )
        ]

    def load_equipment_register_data(self, items):
        self.equipment_register_table.setRowCount(0)

        for item in items:
            if "관리번호" not in item:
                item["관리번호"] = item.get("관리명", "")
            self.add_equipment_register_row(item)

        self.update_register_summary()
        if hasattr(self, "performance_calc_equipment"):
            self.reconcile_performance_calculation_equipment_ids()
            self.refresh_performance_equipment_choices()

    def collect_target_selection_data(self):
        items = []

        for row in range(self.target_table.rowCount()):
            source_combo = self.target_table.cellWidget(row, 2)
            register_row = (
                source_combo.currentData() if source_combo else -1
            )

            target_item = {
                "설비종류": self.target_combo_text(row, 0),
                "점검번호": self.table_item_text(
                    self.target_table, row, 1
                ),
                "장비대장행": (
                    int(register_row)
                    if register_row not in (None, -1)
                    else -1
                ),
            }
            equipment_id = self.equipment_id_for_target_row(row)
            if equipment_id:
                target_item["equipment_id"] = equipment_id
            items.append(target_item)

        return items

    def load_target_selection_data(self, items):
        self.target_table.setRowCount(0)

        for item in items:
            self.add_target_selection_row(item)

        self.refresh_target_table()
        self.reconcile_inspection_result_equipment_ids()

    def register_row_data(self, row):
        equipment_type = self.register_combo_text(row, 0)
        data = {
            "equipment_id": self.equipment_id_for_register_row(
                row, create=True
            ),
            "설비종류": equipment_type,
            "관리번호": self.table_item_text(
                self.equipment_register_table, row, 2
            ),
            "설치위치": self.table_item_text(
                self.equipment_register_table, row, 3
            ),
            "주요사양": self.table_item_text(
                self.equipment_register_table, row, 4
            ),
            "설치연도": self.table_item_text(
                self.equipment_register_table, row, 5
            ),
            "비고": self.table_item_text(
                self.equipment_register_table, row, 6
            ),
        }
        if equipment_type == "냉동기":
            data["세부유형"] = self.register_subtype_code(row)
        return data

    def target_row_data(self, row):
        source_combo = self.target_table.cellWidget(row, 2)
        register_row = (
            source_combo.currentData() if source_combo else -1
        )
        register_data = (
            self.register_row_data(int(register_row))
            if register_row not in (None, -1)
            else {}
        )

        return {
            "설비종류": self.target_combo_text(row, 0),
            "점검번호": self.table_item_text(
                self.target_table, row, 1
            ),
            "장비대장행": register_row,
            "관리번호": register_data.get("관리번호", ""),
            "설치위치": register_data.get("설치위치", ""),
            "주요사양": register_data.get("주요사양", ""),
            "설치연도": register_data.get("설치연도", ""),
            "세부유형": register_data.get("세부유형", ""),
            "equipment_id": self.equipment_id_for_target_row(row),
        }

    def target_key_from_row(self, row):
        equipment_type = self.target_combo_text(row, 0)
        inspection_number = self.table_item_text(
            self.target_table, row, 1
        )
        source_combo = self.target_table.cellWidget(row, 2)
        register_row = (
            source_combo.currentData() if source_combo else -1
        )
        return (
            f"{equipment_type}|{inspection_number}|"
            f"{register_row}|{row}"
        )

    def find_target_data_by_key(self, key):
        for row in range(self.target_table.rowCount()):
            if self.target_key_from_row(row) == key:
                return self.target_row_data(row)
        return None

    def register_combo_text(self, row, column):
        widget = self.equipment_register_table.cellWidget(row, column)
        return widget.currentText().strip() if widget else ""

    def target_combo_text(self, row, column):
        widget = self.target_table.cellWidget(row, column)
        return widget.currentText().strip() if widget else ""

    @staticmethod
    def equipment_code_prefix(name):
        prefixes = {
            "냉동기": "CH",
            "냉각탑": "CT",
            "축열조": "TS",
            "보일러": "BL",
            "열교환기": "HX",
            "팽창탱크": "ET",
            "펌프": "P",
            "신재생에너지설비": "RE",
            "연료전지": "FC",
            "패키지에어컨": "PAC",
            "항온항습기": "CRAC",
            "공기조화기": "AHU",
            "팬코일유닛": "FCU",
            "환기설비": "FAN",
            "필터": "FLT",
            "위생기구설비": "SAN",
            "급수·급탕설비": "WTR",
            "고·저수조": "TK",
            "오·배수 통기 및 우수배수설비": "DRN",
            "오수정화설비": "STP",
            "물 재이용설비": "RWS",
            "배관설비": "PIPE",
            "덕트설비": "DUCT",
            "보온설비": "INS",
            "자동제어설비": "AUTO",
            "방음·방진·내진설비": "VIB",
        }
        return prefixes.get(name, "EQ")

    @staticmethod
    def table_item_text(table, row, column):
        item = table.item(row, column)
        return item.text().strip() if item else ""

    def prepare_report_page(self):
        site_name = self.site_name.text().strip() or "현장명미입력"
        default_name = (
            f"{self.safe_filename(site_name)}_기계설비성능점검_계획_및_보고서"
        )

        if not self.report_filename.text().strip():
            self.report_filename.setText(default_name)

        if not self.report_output_dir.text().strip():
            self.report_output_dir.setText(
                str(Path.cwd() / "생성보고서")
            )

        if not self.original_sample_path.text().strip():
            original_candidates = [
                Path.cwd() / "templates" / "기계설비성능점검_기본템플릿.hwp",
                Path.cwd() / "기계설비성능점검_기본템플릿.hwp",
                Path(__file__).resolve().parent / "templates" / "기계설비성능점검_기본템플릿.hwp",
                Path(__file__).resolve().parent / "기계설비성능점검_기본템플릿.hwp",
            ]

            for candidate in original_candidates:
                if candidate.exists():
                    self.original_sample_path.setText(str(candidate))
                    break

        if not self.report_template_path.text().strip():
            mapped_candidates = [
                Path.cwd() / "templates" / "기계설비성능점검_매핑템플릿.hwp",
                Path.cwd() / "기계설비성능점검_매핑템플릿.hwp",
                Path(__file__).resolve().parent / "templates" / "기계설비성능점검_매핑템플릿.hwp",
                Path(__file__).resolve().parent / "기계설비성능점검_매핑템플릿.hwp",
            ]

            for candidate in mapped_candidates:
                if candidate.exists():
                    self.report_template_path.setText(str(candidate))
                    break

        self.preview_report_text()

    def select_report_output_dir(self):
        current = self.report_output_dir.text().strip() or str(Path.cwd())
        folder = QFileDialog.getExistingDirectory(
            self,
            "보고서 출력폴더 선택",
            current,
        )

        if folder:
            self.report_output_dir.setText(folder)

    def select_original_sample(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "기존 보고서 원본 선택",
            str(Path.cwd()),
            "한글 문서 (*.hwp *.hwpx)",
        )

        if file_path:
            self.original_sample_path.setText(file_path)

    def select_report_template(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "HWP 템플릿 선택",
            str(Path.cwd()),
            "한글 문서 (*.hwp *.hwpx)",
        )

        if file_path:
            self.report_template_path.setText(file_path)

    @staticmethod
    def sanitize_field_name(name):
        return (
            str(name)
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
            .replace("(", "")
            .replace(")", "")
            .replace("·", "_")
        )

    def hwp_find_and_create_field(
        self,
        hwp,
        find_text,
        field_name,
        direction="",
    ):
        hwp.HAction.Run("MoveDocBegin")

        if not self.hwp_find_text(hwp, find_text):
            return False

        # RepeatFind가 찾은 문자열을 선택한 상태이므로 삭제 후
        # 같은 위치에 누름틀 필드를 만든다.
        try:
            hwp.HAction.Run("Delete")
        except Exception:
            pass

        try:
            return bool(
                hwp.CreateField(
                    Direction=direction or field_name,
                    memo=field_name,
                    name=field_name,
                )
            )
        except TypeError:
            return bool(
                hwp.CreateField(
                    direction or field_name,
                    field_name,
                    field_name,
                )
            )

    def hwp_set_cell_field_by_anchor(
        self,
        hwp,
        anchor_text,
        move_count,
        field_name,
    ):
        hwp.HAction.Run("MoveDocBegin")

        if not self.hwp_find_text(hwp, anchor_text):
            return False

        try:
            for _ in range(move_count):
                hwp.HAction.Run("TableRightCell")

            return bool(
                hwp.SetCurFieldName(
                    field_name,
                    0,
                    "",
                    field_name,
                )
            )
        except Exception:
            return False

    def standard_field_names(self):
        names = [
            "P01_현장명",
            "P01_제출일",
            "P02_현장명",
            "P02_제출일",
            "P07_현장명",
            "P07_점검일자",
            "P07_관리주체",
            "P07_유지관리자1",
            "P07_유지관리자2",
            "P12_용도",
            "P12_관리주체주소",
            "P12_유지관리자1성명",
            "P12_유지관리자1등급",
            "P12_유지관리자1선임일",
            "P12_유지관리자1교육수료일",
            "P12_유지관리자2성명",
            "P12_유지관리자2등급",
            "P12_유지관리자2선임일",
            "P12_유지관리자2교육수료일",
            "P12_유지관리조직도",
        ]

        for row in self.collect_page13_data():
            if row.get("항목", "").strip():
                names.append(
                    "P13_" + self.sanitize_field_name(
                        row["항목"]
                    )
                )

        for row in self.collect_emergency_data():
            anchor = (
                row.get("기관성명", "").strip()
                or row.get("구분", "").strip()
            )
            if anchor:
                names.append(
                    "P18_" + self.sanitize_field_name(anchor)
                    + "_전화번호"
                )

        for item in self.collect_equipment_data():
            equipment_name = item.get("설비명", "").strip()
            if not equipment_name:
                continue

            prefix = (
                "P25_"
                + self.sanitize_field_name(equipment_name)
            )
            names.extend(
                [
                    prefix + "_대상여부",
                    prefix + "_전체수량",
                    prefix + "_점검수량",
                ]
            )

        return names

    def create_field_template(self):
        source_text = self.report_template_path.text().strip()

        if not source_text or not Path(source_text).exists():
            QMessageBox.warning(
                self,
                "템플릿 확인",
                "먼저 기본 자동화템플릿 HWP를 선택하십시오.",
            )
            return

        source_path = Path(source_text).resolve()
        output_path = (
            source_path.parent
            / f"{source_path.stem}_필드연결{source_path.suffix}"
        )

        try:
            shutil.copy2(source_path, output_path)
            import win32com.client
        except Exception as error:
            QMessageBox.critical(
                self,
                "필드 템플릿 준비 실패",
                str(error),
            )
            return

        hwp = None
        audit = []

        # 화면에서 확인된 표식과 고정값을 실제 누름틀 필드로 전환
        text_fields = [
            ("{{현장명}}", "P07_현장명"),
            ("{{ 현장명 }}", "P07_현장명"),
            ("{{관리주체}}", "P07_관리주체"),
            ("{{ 관리주체 }}", "P07_관리주체"),
            (
                "{{기계설비유지관리자1}}",
                "P07_유지관리자1",
            ),
            (
                "{{기계설비유지 관리자1}}",
                "P07_유지관리자1",
            ),
            ("테스트유지관리자2", "P07_유지관리자2"),
            ("2026.   07.     .", "P07_점검일자"),
            ("2026.  07.    .", "P07_점검일자"),
            ("2026. 07.   .", "P07_점검일자"),
            ("2026. 07.  .", "P07_점검일자"),
            ("2026. 07. .", "P07_점검일자"),
            ("문화및집회시설", "P12_용도"),
            ("문화 및 집회시설", "P12_용도"),
            (
                "서울특별시 예시구 예시로 00 테스트센터",
                "P12_관리주체주소",
            ),
            ("테스트유지관리자1", "P12_유지관리자1성명"),
            ("2023.08.09", "P12_유지관리자1선임일"),
            (
                "2023.10.03",
                "P12_유지관리자1교육수료일",
            ),
            ("2026.06.26", "P12_유지관리자2선임일"),
            (
                "2026.07.00",
                "P12_유지관리자2교육수료일",
            ),
        ]

        try:
            hwp = win32com.client.Dispatch(
                "HWPFrame.HwpObject"
            )
            hwp.XHwpWindows.Item(0).Visible = True

            if hwp.Open(str(output_path)) is False:
                raise RuntimeError(
                    "복사된 템플릿을 열지 못했습니다."
                )

            for find_text, field_name in text_fields:
                try:
                    changed = self.hwp_find_and_create_field(
                        hwp,
                        find_text,
                        field_name,
                    )
                except Exception:
                    changed = False

                audit.append(
                    f"{field_name}: "
                    f"{'생성' if changed else '문구없음'} "
                    f"[{find_text}]"
                )

            # 13페이지: 항목명 오른쪽 셀을 셀필드로 지정
            for row in self.collect_page13_data():
                item_name = row.get("항목", "").strip()
                if not item_name:
                    continue

                field_name = (
                    "P13_"
                    + self.sanitize_field_name(item_name)
                )
                changed = self.hwp_set_cell_field_by_anchor(
                    hwp,
                    item_name,
                    1,
                    field_name,
                )
                audit.append(
                    f"{field_name}: "
                    f"{'생성' if changed else '앵커없음'}"
                )

            # 18페이지: 기관명 오른쪽 전화번호 셀
            for row in self.collect_emergency_data():
                anchor = (
                    row.get("기관성명", "").strip()
                    or row.get("구분", "").strip()
                )
                if not anchor:
                    continue

                field_name = (
                    "P18_"
                    + self.sanitize_field_name(anchor)
                    + "_전화번호"
                )
                changed = self.hwp_set_cell_field_by_anchor(
                    hwp,
                    anchor,
                    1,
                    field_name,
                )
                audit.append(
                    f"{field_name}: "
                    f"{'생성' if changed else '앵커없음'}"
                )

            # 25페이지: 설비명 기준 대상여부, 전체수량, 점검수량
            for item in self.collect_equipment_data():
                equipment_name = item.get("설비명", "").strip()
                if not equipment_name:
                    continue

                prefix = (
                    "P25_"
                    + self.sanitize_field_name(equipment_name)
                )

                offsets = [
                    (1, prefix + "_대상여부"),
                    (2, prefix + "_전체수량"),
                    (5, prefix + "_점검수량"),
                ]

                for offset, field_name in offsets:
                    changed = self.hwp_set_cell_field_by_anchor(
                        hwp,
                        equipment_name,
                        offset,
                        field_name,
                    )
                    audit.append(
                        f"{field_name}: "
                        f"{'생성' if changed else '앵커없음'}"
                    )

            hwp.SaveAs(str(output_path), "HWP", "")

            audit_path = output_path.with_name(
                output_path.stem + "_필드생성결과.txt"
            )
            audit_path.write_text(
                "\n".join(audit),
                encoding="utf-8",
            )

            self.report_template_path.setText(
                str(output_path)
            )

            QMessageBox.information(
                self,
                "필드 템플릿 생성 완료",
                f"필드 템플릿:\n{output_path}\n\n"
                f"생성 결과:\n{audit_path}\n\n"
                "이제 '필드 연결상태 확인' 후 보고서를 생성하십시오.",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "필드 템플릿 생성 실패",
                str(error),
            )

        finally:
            if hwp is not None:
                try:
                    hwp.Quit()
                except Exception:
                    pass

    def check_template_fields(self):
        template_text = self.report_template_path.text().strip()

        if not template_text or not Path(template_text).exists():
            QMessageBox.warning(
                self,
                "템플릿 확인",
                "필드 템플릿을 먼저 선택하거나 생성하십시오.",
            )
            return

        try:
            import win32com.client
            hwp = win32com.client.Dispatch(
                "HWPFrame.HwpObject"
            )
            hwp.XHwpWindows.Item(0).Visible = False

            if hwp.Open(str(Path(template_text).resolve())) is False:
                raise RuntimeError("템플릿을 열지 못했습니다.")

            field_list = hwp.GetFieldList(0, 0) or ""
            available = {
                item
                for item in str(field_list).replace(
                    "\r\n", "\x02"
                ).split("\x02")
                if item
            }

            required = self.standard_field_names()
            missing = [
                name
                for name in required
                if name not in available
            ]

            hwp.Quit()

            if missing:
                QMessageBox.warning(
                    self,
                    "필드 연결 미완료",
                    "다음 필드가 없습니다.\n\n"
                    + "\n".join(missing[:40]),
                )
            else:
                QMessageBox.information(
                    self,
                    "필드 연결 정상",
                    f"필수 필드 {len(required)}개가 모두 확인됐습니다.",
                )

        except Exception as error:
            QMessageBox.critical(
                self,
                "필드 확인 실패",
                str(error),
            )

    def build_field_values(self):
        values = self.build_front_page_values()

        field_values = {
            "P01_현장명": values.get("현장명", ""),
            "P01_제출일": values.get("작성일한글", ""),
            "P02_현장명": values.get("현장명", ""),
            "P02_제출일": values.get("작성일한글", ""),
            "P07_현장명": values.get("현장명", ""),
            "P07_점검일자": values.get("작성일점", ""),
            "P07_관리주체": values.get("관리주체", ""),
            "P07_유지관리자1": values.get(
                "기계설비유지관리자1", ""
            ),
            "P07_유지관리자2": values.get(
                "기계설비유지관리자2", ""
            ),
            "P12_용도": values.get("용도", ""),
            "P12_관리주체주소": values.get(
                "관리주체주소", ""
            ),
            "P12_유지관리자1성명": values.get(
                "기계설비유지관리자1", ""
            ),
            "P12_유지관리자1등급": values.get(
                "유지관리자등급1", ""
            ),
            "P12_유지관리자1선임일": values.get(
                "유지관리자1선임일", ""
            ),
            "P12_유지관리자1교육수료일": values.get(
                "유지관리자1교육수료일", ""
            ),
            "P12_유지관리자2성명": values.get(
                "기계설비유지관리자2", ""
            ),
            "P12_유지관리자2등급": values.get(
                "유지관리자등급2", ""
            ),
            "P12_유지관리자2선임일": values.get(
                "유지관리자2선임일", ""
            ),
            "P12_유지관리자2교육수료일": values.get(
                "유지관리자2교육수료일", ""
            ),
            "P12_유지관리조직도": values.get(
                "유지관리조직도", ""
            ),
        }

        for row in self.collect_page13_data():
            item_name = row.get("항목", "").strip()
            if not item_name:
                continue

            field_name = (
                "P13_"
                + self.sanitize_field_name(item_name)
            )
            field_values[field_name] = {
                "유": "○",
                "무": "×",
                "해당없음": "/",
            }.get(row.get("유무", ""), "")

        for row in self.collect_emergency_data():
            anchor = (
                row.get("기관성명", "").strip()
                or row.get("구분", "").strip()
            )
            if not anchor:
                continue

            field_name = (
                "P18_"
                + self.sanitize_field_name(anchor)
                + "_전화번호"
            )
            field_values[field_name] = row.get(
                "전화번호", ""
            )

        for item in self.collect_equipment_data():
            equipment_name = item.get("설비명", "").strip()
            if not equipment_name:
                continue

            prefix = (
                "P25_"
                + self.sanitize_field_name(equipment_name)
            )
            selected = bool(item.get("선택"))

            field_values[prefix + "_대상여부"] = (
                "○" if selected else "-"
            )
            field_values[prefix + "_전체수량"] = (
                str(item.get("전체수량", 0))
                if selected
                else "-"
            )
            field_values[prefix + "_점검수량"] = (
                str(item.get("점검수량", 0))
                if selected
                else "-"
            )

        return field_values

    def put_all_field_values(self, hwp):
        field_values = self.build_field_values()

        field_names = []
        texts = []

        for name, value in field_values.items():
            if hwp.FieldExist(name):
                field_names.append(name)
                texts.append(str(value))

        if not field_names:
            raise RuntimeError(
                "템플릿에서 입력 가능한 필드를 찾지 못했습니다. "
                "'필드 템플릿 만들기'를 먼저 실행하십시오."
            )

        hwp.PutFieldText(
            "\x02".join(field_names),
            "\x02".join(texts),
        )

        return field_names

    def collect_report_criterion_preflight_issues(self):
        """Collect criterion issues without mutating inspection data."""
        issues = []
        for target_row in self.valid_photo_target_rows():
            target_key = self.target_key_from_row(target_row)
            target_data = self.target_row_data(target_row)
            equipment_type = target_data.get("설비종류", "")
            management_number = target_data.get("관리번호", "")
            inspection_number = target_data.get("점검번호", "")
            result_rows = self.inspection_results.get(target_key, [])
            if not isinstance(result_rows, list):
                result_rows = []
            result_by_number = {
                str(row.get("번호", "")): row
                for row in result_rows
                if isinstance(row, dict) and str(row.get("번호", ""))
            }

            for detail_row, item_data in enumerate(
                self._inspection_db.get(equipment_type, [])
            ):
                criteria = self.measurement_metadata(item_data).get(
                    "criteria", []
                )
                if not criteria:
                    continue
                item_number = str(item_data.get("no", ""))
                result = result_by_number.get(item_number)
                if result is None and detail_row < len(result_rows):
                    candidate = result_rows[detail_row]
                    candidate_number = (
                        str(candidate.get("번호", ""))
                        if isinstance(candidate, dict)
                        else ""
                    )
                    if (
                        isinstance(candidate, dict)
                        and candidate_number in {"", item_number}
                    ):
                        result = candidate
                result = result if isinstance(result, dict) else {}
                results_present = (
                    "criteria_results" in result
                    and isinstance(result.get("criteria_results"), list)
                    and bool(result.get("criteria_results"))
                )
                row_issues = self.criterion_preflight_issues(
                    criteria,
                    result.get("criteria_results"),
                    result.get("판정", "미점검"),
                    results_present,
                )
                for issue in row_issues:
                    enriched = dict(issue)
                    enriched.update(
                        {
                            "target_key": target_key,
                            "equipment_id": target_data.get("equipment_id", ""),
                            "equipment_type": equipment_type,
                            "management_number": management_number,
                            "inspection_number": inspection_number,
                            "item_number": item_number,
                            "item_name": item_data.get("name", ""),
                            "detail_row": detail_row,
                        }
                    )
                    issues.append(enriched)
        return issues

    @staticmethod
    def format_report_preflight_issue(issue):
        location = " / ".join(
            part
            for part in (
                str(issue.get("equipment_type", "") or "설비 미상"),
                str(issue.get("management_number", "") or "관리번호 미지정"),
                (
                    f"점검번호 {issue.get('inspection_number')}"
                    if str(issue.get("inspection_number", "")).strip()
                    else ""
                ),
                (
                    f"{issue.get('item_number')}번 {issue.get('item_name', '')}"
                    if str(issue.get("item_number", "")).strip()
                    else str(issue.get("item_name", ""))
                ),
                str(issue.get("criterion_name", "") or ""),
            )
            if part
        )
        return f"{location}: {issue.get('message', '')}"

    def show_report_preflight_dialog(self, issues):
        errors = [item for item in issues if item.get("severity") == "error"]
        warnings = [item for item in issues if item.get("severity") != "error"]

        dialog = QDialog(self)
        dialog.setWindowTitle("보고서 생성 전 확인사항")
        dialog.resize(820, 520)
        layout = QVBoxLayout(dialog)
        summary = QLabel(
            f"오류 {len(errors)}건 / 경고 {len(warnings)}건\n"
            "최종판정은 자동으로 변경되지 않습니다. 내용을 확인한 뒤 계속 여부를 선택하십시오."
        )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        issue_list = QListWidget()
        ordered = errors + warnings
        for issue in ordered:
            prefix = "[오류]" if issue.get("severity") == "error" else "[경고]"
            issue_list.addItem(
                f"{prefix} {self.format_report_preflight_issue(issue)}"
            )
        if ordered:
            issue_list.setCurrentRow(0)
        layout.addWidget(issue_list, 1)

        buttons = QHBoxLayout()
        move_button = QPushButton("해당 항목으로 이동")
        continue_button = QPushButton("그래도 계속")
        cancel_button = QPushButton("취소")
        buttons.addWidget(move_button)
        buttons.addStretch()
        buttons.addWidget(continue_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

        action = {"value": "cancel"}

        def choose(value):
            action["value"] = value
            dialog.accept()

        move_button.clicked.connect(lambda: choose("move"))
        continue_button.clicked.connect(lambda: choose("continue"))
        cancel_button.clicked.connect(dialog.reject)
        dialog.exec()
        selected_row = issue_list.currentRow()
        selected = (
            ordered[selected_row]
            if 0 <= selected_row < len(ordered)
            else (ordered[0] if ordered else None)
        )
        return action["value"], selected

    def move_to_report_preflight_issue(self, issue):
        if not isinstance(issue, dict):
            return False
        target_key = issue.get("target_key")
        self.menu.setCurrentRow(3)
        self.inspection_tabs.setCurrentIndex(2)
        self.refresh_target_table()
        target_index = self.detail_equipment_combo.findData(target_key)
        if target_index < 0:
            return False
        self.detail_equipment_combo.setCurrentIndex(target_index)
        detail_row = issue.get("detail_row")
        if isinstance(detail_row, int) and 0 <= detail_row < self.inspection_detail_table.rowCount():
            self.inspection_detail_table.setCurrentCell(detail_row, 0)
            self.refresh_criteria_results_panel(detail_row)
        return True

    def validate_report_data(self, show_message=True):
        errors = []
        warnings = []

        site_data = self.collect_site_data()

        for field in ["현장명", "주소", "관리주체"]:
            if not str(site_data.get(field, "")).strip():
                errors.append(f"현장정보: {field} 미입력")

        basis = site_data.get("성능점검기준구분", "연면적")

        if basis == "세대수":
            try:
                households = int(site_data.get("세대수", 0))
            except (TypeError, ValueError):
                households = 0

            if households <= 0:
                errors.append("현장정보: 세대수 미입력")
        else:
            try:
                area = float(
                    str(site_data.get("연면적", ""))
                    .replace(",", "")
                    .strip()
                )
            except (TypeError, ValueError):
                area = 0

            if area <= 0:
                errors.append("현장정보: 연면적 미입력")

        if self.count_selected_equipment() == 0:
            errors.append("설비현황: 선택된 설비가 없음")

        if self.technician_table.rowCount() == 0:
            errors.append("성능점검 기술자: 입력된 기술자가 없음")

        if self.equipment_register_table.rowCount() == 0:
            errors.append("장비대장: 등록된 장비가 없음")

        valid_targets = self.valid_photo_target_rows()

        if not valid_targets:
            errors.append("점검대상 선정: 관리번호가 선택된 장비가 없음")

        incomplete_results = 0

        for row in valid_targets:
            key = self.target_key_from_row(row)
            results = self.inspection_results.get(key, [])

            if not results:
                incomplete_results += 1
                continue

            if any(item.get("판정", "미점검") == "미점검" for item in results):
                incomplete_results += 1

        if incomplete_results:
            warnings.append(
                f"점검결과 미완료 또는 미점검 장비 {incomplete_results}건"
            )

        if not self.photo_records:
            warnings.append("등록된 점검사진이 없음")

        output_dir = self.report_output_dir.text().strip()

        if not output_dir:
            errors.append("보고서 출력폴더 미지정")

        filename = self.report_filename.text().strip()

        if not filename:
            errors.append("보고서 파일명 미입력")

        original_path = self.original_sample_path.text().strip()

        if not original_path:
            errors.append("완성본 참고용 원본 HWP 미지정")
        elif not Path(original_path).exists():
            errors.append("완성본 참고용 원본 HWP를 찾을 수 없음")

        template_path = self.report_template_path.text().strip()

        if not template_path:
            errors.append(
                "자동화 매핑템플릿 미지정. 먼저 '완성본 비교·매핑템플릿 생성'을 실행하십시오."
            )
        elif not Path(template_path).exists():
            errors.append("지정한 자동화 매핑템플릿을 찾을 수 없음")


        if (not self.generate_hwp_checkbox.isChecked() and not self.generate_pdf_checkbox.isChecked()):
            errors.append("출력형식 HWP 또는 PDF를 하나 이상 선택해야 함")

        if errors:
            text = "검증 실패\n" + "\n".join(f"• {item}" for item in errors)

            if warnings:
                text += "\n\n주의사항\n" + "\n".join(
                    f"• {item}" for item in warnings
                )

            self.report_validation_label.setText(text)
            self.report_validation_label.setStyleSheet(
                "padding: 8px; background: #fee2e2; border: 1px solid #ef4444;"
            )

            if show_message:
                QMessageBox.warning(
                    self,
                    "보고서 생성 검증",
                    text,
                )

            return False

        text = "검증 완료"

        if warnings:
            text += "\n" + "\n".join(f"• {item}" for item in warnings)

        self.report_validation_label.setText(text)
        self.report_validation_label.setStyleSheet(
            "padding: 8px; background: #dcfce7; border: 1px solid #22c55e;"
        )

        if show_message:
            QMessageBox.information(
                self,
                "보고서 생성 검증",
                text,
            )

        return True

    def build_report_text(self):
        site = self.collect_site_data()
        technicians = self.collect_technician_data()
        equipment = self.collect_equipment_data()
        register = self.collect_equipment_register_data()
        targets = self.collect_target_selection_data()

        lines = []

        lines.append("기계설비 성능점검 보고서")
        lines.append("=" * 42)
        lines.append("")
        lines.append("1. 현장 개요")
        lines.append(f"현장명: {site.get('현장명', '')}")
        lines.append(f"주소: {site.get('주소', '')}")
        lines.append(f"건축물 용도: {site.get('용도', '')}")
        basis = site.get("성능점검기준구분", "연면적")
        if basis == "연면적":
            lines.append(
                f"성능점검 기준: 연면적 {site.get('연면적', '')} ㎡"
            )
        else:
            lines.append(
                f"성능점검 기준: {site.get('세대수', 0)} 세대"
            )
        lines.append(
            f"층수: 지상 {site.get('지상층수', 0)}층 / 지하 {site.get('지하층수', 0)}층"
        )
        lines.append(f"관리주체: {site.get('관리주체', '')}")
        lines.append(
            f"점검기간: {site.get('점검시작일', '')} ~ {site.get('점검종료일', '')}"
        )
        lines.append(f"보고서 작성일: {site.get('보고서작성일', '')}")
        lines.append("")

        lines.append("2. 성능점검 수행기관")
        lines.append(f"성능점검업체: {COMPANY_NAME}")

        for technician in technicians:
            lines.append(
                f"- {technician.get('구분', '')}: "
                f"{technician.get('성명', '')} / "
                f"{technician.get('등급', '')} / "
                f"{technician.get('수첩번호', '')}"
            )

        lines.append("")
        lines.append("3. 서울형 품질관리 보강자료")
        lines.append(
            f"- 시스템 검토: "
            f"{'작성' if self.system_operation_review.toPlainText().strip() else '미작성'}"
        )
        lines.append(
            f"- 노후도 분석: {self.aging_table.rowCount()}건"
        )
        lines.append(
            f"- 성능개선 계획: {self.improvement_table.rowCount()}건"
        )
        lines.append(
            f"- 에너지 분석: "
            f"{'작성' if any(self.energy_table.item(r, 1).text().strip() for r in range(self.energy_table.rowCount())) else '미작성'}"
        )
        lines.append("")
        lines.append("4. 설비현황")

        for item in equipment:
            if not item.get("선택"):
                continue

            lines.append(
                f"- {item.get('설비명')}: 전체 {item.get('전체수량')} "
                f"{item.get('단위')} / 산정대상 {item.get('산정대상수량')} / "
                f"점검수량 {item.get('점검수량')}"
            )

        lines.append("")
        lines.append("4. 장비대장")

        for item in register:
            lines.append(
                f"- {item.get('설비종류', '')} / "
                f"관리번호 {item.get('관리번호', '')} / "
                f"위치 {item.get('설치위치', '') or '-'} / "
                f"사양 {item.get('주요사양', '') or '-'} / "
                f"설치연도 {item.get('설치연도', '') or '-'}"
            )

        lines.append("")
        lines.append("5. 점검대상 및 결과")

        for row in range(self.target_table.rowCount()):
            target = self.target_row_data(row)
            key = self.target_key_from_row(row)
            results = self.inspection_results.get(key, [])

            lines.append("")
            lines.append(
                f"[{target.get('설비종류', '')}] "
                f"점검번호 {target.get('점검번호', '')} / "
                f"관리번호 {target.get('관리번호', '') or '-'}"
            )
            lines.append(
                f"설치위치: {target.get('설치위치', '') or '-'} / "
                f"주요사양: {target.get('주요사양', '') or '-'}"
            )

            if not results:
                lines.append("- 점검결과 미입력")
                continue

            for item in results:
                value_text = item.get("측정확인값", "") or "-"
                design_text = item.get("설계정격값", "") or "-"
                lines.append(
                    f"- {item.get('번호', '')}. {item.get('점검내용', '')} | "
                    f"구분 {item.get('입력구분', '')} | "
                    f"설계·정격 {design_text} | "
                    f"확인·측정 {value_text} | "
                    f"판정 {item.get('판정', '')}"
                )

                opinion = item.get("기술적소견", "").strip()

                if opinion:
                    lines.append(f"  기술적 소견: {opinion}")

        lines.append("")
        lines.append("6. 사진자료")

        if not self.photo_records:
            lines.append("- 등록 사진 없음")
        else:
            for index, photo in enumerate(self.photo_records, start=1):
                lines.append(
                    f"{index}. {photo.get('장비표시', '')} / "
                    f"{photo.get('점검항목', '')} / "
                    f"{photo.get('사진구분', '')}"
                )
                lines.append(
                    f"   파일: {photo.get('원본파일명', '')}"
                )
                caption = photo.get("설명", "").strip()

                if caption:
                    lines.append(f"   설명: {caption}")

        lines.append("")
        lines.append("7. 종합의견")
        action_required = 0
        uninspected = 0

        for result_rows in self.inspection_results.values():
            for item in result_rows:
                judgment = item.get("판정", "")

                if self.is_final_fail(judgment):
                    action_required += 1
                elif judgment == "미점검":
                    uninspected += 1

        lines.append(
            f"조치필요 항목: {action_required}건 / 미점검 항목: {uninspected}건"
        )
        lines.append("")
        lines.append("※ 본 문서는 프로그램에서 생성한 1차 자동작성 초안입니다.")

        return "\n".join(lines)

    def preview_report_text(self):
        preview_text = self.build_report_text()

        # setPlainText가 기존 커서 위치를 복원하는 과정에서
        # 빈 문서 범위를 벗어나는 Qt 경고가 발생할 수 있으므로,
        # 문서 내용을 직접 교체하고 커서를 시작 위치로 초기화한다.
        self.report_preview.document().setPlainText(preview_text)
        cursor = QTextCursor(self.report_preview.document())
        cursor.movePosition(QTextCursor.Start)
        self.report_preview.setTextCursor(cursor)

    def hwp_insert_text(self, hwp, text):
        hwp.HAction.GetDefault(
            "InsertText",
            hwp.HParameterSet.HInsertText.HSet,
        )
        hwp.HParameterSet.HInsertText.Text = text
        hwp.HAction.Execute(
            "InsertText",
            hwp.HParameterSet.HInsertText.HSet,
        )

    @staticmethod
    def korean_date_text(date_text):
        date_value = QDate.fromString(date_text, "yyyy-MM-dd")

        if not date_value.isValid():
            return date_text

        return (
            f"{date_value.year()}년 "
            f"{date_value.month():02d}월 "
            f"{date_value.day():02d}일"
        )

    @staticmethod
    def dotted_date_text(date_text):
        date_value = QDate.fromString(date_text, "yyyy-MM-dd")

        if not date_value.isValid():
            return date_text

        return (
            f"{date_value.year()}. "
            f"{date_value.month():02d}. "
            f"{date_value.day():02d}."
        )

    def build_page25_values(self):
        values = {}
        equipment_rows = self.collect_equipment_data()

        for index, item in enumerate(equipment_rows, start=1):
            key = item.get("설비명", "").replace(" ", "")
            selected = bool(item.get("선택"))
            total = item.get("전체수량", 0)
            inspection = item.get("점검수량", 0)
            target = "대상" if selected else "비대상"

            values[f"P25_{index}_설비명"] = item.get("설비명", "")
            values[f"P25_{index}_대상여부"] = target
            values[f"P25_{index}_전체수량"] = str(total)
            values[f"P25_{index}_점검수량"] = str(
                inspection if selected else 0
            )
            values[f"P25_{key}_대상여부"] = target
            values[f"P25_{key}_전체수량"] = str(total)
            values[f"P25_{key}_점검수량"] = str(
                inspection if selected else 0
            )

        return values

    @staticmethod
    def hwp_replace_all(hwp, find_text, replace_text):
        if not find_text:
            return

        hwp.HAction.GetDefault(
            "AllReplace",
            hwp.HParameterSet.HFindReplace.HSet,
        )
        parameter = hwp.HParameterSet.HFindReplace
        parameter.FindString = str(find_text)
        parameter.ReplaceString = str(replace_text)
        parameter.IgnoreMessage = 1
        parameter.Direction = 2
        parameter.FindType = 1
        hwp.HAction.Execute(
            "AllReplace",
            hwp.HParameterSet.HFindReplace.HSet,
        )

    def format_area(self, value):
        text = str(value or "").replace(",", "").strip()

        try:
            return f"{float(text):,.2f}"
        except ValueError:
            return text

    def build_equipment_summary_text(self):
        rows = []

        for item in self.collect_equipment_data():
            if not item.get("선택"):
                continue

            rows.append(
                f"{item.get('설비명', '')}: "
                f"전체 {item.get('전체수량', 0)}{item.get('단위', '')}, "
                f"산정대상 {item.get('산정대상수량', 0)}, "
                f"점검 {item.get('점검수량', 0)}"
            )

        return "\n".join(rows)

    def build_target_summary_text(self):
        rows = []

        for row in self.valid_photo_target_rows():
            target = self.target_row_data(row)
            rows.append(
                f"{target.get('설비종류', '')} "
                f"점검번호 {target.get('점검번호', '')}, "
                f"관리번호 {target.get('관리번호', '')}, "
                f"위치 {target.get('설치위치', '') or '-'}"
            )

        return "\n".join(rows)

    def build_technician_summary_text(self):
        rows = []

        for item in self.collect_technician_data():
            name = item.get("성명", "").strip()

            if not name:
                continue

            rows.append(
                f"{item.get('구분', '')} {name} "
                f"({item.get('등급', '')}, {item.get('수첩번호', '')})"
            )

        return "\n".join(rows)

    def build_front_page_values(self):
        site = self.collect_site_data()
        technicians = self.collect_technician_data()

        responsible = ""
        participants = []

        for item in technicians:
            name = item.get("성명", "").strip()

            if not name:
                continue

            if item.get("구분") == "책임기술자" and not responsible:
                responsible = name
            else:
                participants.append(name)

        floor_text = (
            f"지상 {site.get('지상층수', 0)}층 / "
            f"지하 {site.get('지하층수', 0)}층"
        )

        inspection_period = (
            f"{site.get('점검시작일', '')} ~ "
            f"{site.get('점검종료일', '')}"
        )

        report_date_text = site.get("보고서작성일", "")
        report_date = QDate.fromString(
            report_date_text, "yyyy-MM-dd"
        )

        if report_date.isValid():
            report_year = str(report_date.year())
            report_year_month = (
                f"{report_date.year()}년 "
                f"{report_date.month():02d}월"
            )
            report_year_month_dot = (
                f"{report_date.year()}. "
                f"{report_date.month():02d}."
            )
            report_korean_date = (
                f"{report_date.year()}년 "
                f"{report_date.month():02d}월 "
                f"{report_date.day():02d}일"
            )
            report_dotted_date = (
                f"{report_date.year()}. "
                f"{report_date.month():02d}. "
                f"{report_date.day():02d}."
            )
        else:
            report_year = ""
            report_year_month = ""
            report_year_month_dot = ""
            report_korean_date = report_date_text
            report_dotted_date = report_date_text

        reference_text = site.get("성능점검기준일", "")
        reference_date = QDate.fromString(
            reference_text, "yyyy-MM-dd"
        )

        if reference_date.isValid():
            reference_korean_date = (
                f"{reference_date.year()}년 "
                f"{reference_date.month():02d}월 "
                f"{reference_date.day():02d}일"
            )
            reference_dotted_date = (
                f"{reference_date.year()}. "
                f"{reference_date.month():02d}. "
                f"{reference_date.day():02d}."
            )
        else:
            reference_korean_date = reference_text
            reference_dotted_date = reference_text

        start_text = site.get("점검시작일", "")
        start_date = QDate.fromString(start_text, "yyyy-MM-dd")

        if start_date.isValid():
            start_dotted_date = (
                f"{start_date.year()}. "
                f"{start_date.month():02d}. "
                f"{start_date.day():02d}."
            )
        else:
            start_dotted_date = start_text

        return {
            "현장명": site.get("현장명", ""),
            "건축물명": site.get("현장명", ""),
            "건축물 명": site.get("현장명", ""),
            "주소": site.get("주소", ""),
            "소재지": site.get("주소", ""),
            "연면적": self.format_area(site.get("연면적", "")),
            "건축물용도": site.get("용도", ""),
            "주용도": site.get("용도", ""),
            "용도": site.get("용도", ""),
            "세대수": site.get("세대수", 0),
            "층수": floor_text,
            "지상층수": site.get("지상층수", 0),
            "지하층수": site.get("지하층수", 0),
            "준공일": site.get("준공일", ""),
            "성능점검기준일": site.get("성능점검기준일", ""),
            "성능점검 기준일": site.get("성능점검기준일", ""),
            "성능점검기준일한글": reference_korean_date,
            "성능점검기준일점": reference_dotted_date,
            "점검기간": inspection_period,
            "성능점검기간": inspection_period,
            "성능점검 기간": inspection_period,
            "점검시작일": site.get("점검시작일", ""),
            "점검시작일점": start_dotted_date,
            "점검종료일": site.get("점검종료일", ""),
            "보고서작성일": site.get("보고서작성일", ""),
            "보고서 작성일": site.get("보고서작성일", ""),
            "작성일": site.get("보고서작성일", ""),
            "작성연도": report_year,
            "작성년월": report_year_month,
            "작성년월점": report_year_month_dot,
            "작성일한글": report_korean_date,
            "작성일점": report_dotted_date,
            "관리주체": site.get("관리주체", ""),
            "관리주체주소": site.get("관리주체주소", ""),
            "대표자": site.get("대표자담당자", ""),
            "담당자": site.get("대표자담당자", ""),
            "전화번호": site.get("전화번호", ""),
            "기계설비유지관리자": site.get(
                "기계설비유지관리자", ""
            ),
            "기계설비유지관리자1": site.get(
                "기계설비유지관리자", ""
            ),
            "유지관리자": site.get("기계설비유지관리자", ""),
            "유지관리자등급": site.get("유지관리자등급", ""),
            "유지관리자등급1": site.get("유지관리자등급", ""),
            "기계설비유지관리자2": site.get(
                "기계설비유지관리자2", ""
            ),
            "유지관리자2": site.get("기계설비유지관리자2", ""),
            "유지관리자등급2": (
                site.get("유지관리자등급2", "")
                if site.get("기계설비유지관리자2", "")
                else ""
            ),
            "유지관리자1선임일": site.get("유지관리자1선임일", ""),
            "유지관리자1교육수료일": site.get(
                "유지관리자1교육수료일", ""
            ),
            "유지관리자2선임일": (
                site.get("유지관리자2선임일", "")
                if site.get("기계설비유지관리자2", "")
                else ""
            ),
            "유지관리자2교육수료일": (
                site.get("유지관리자2교육수료일", "")
                if site.get("기계설비유지관리자2", "")
                else ""
            ),
            "유지관리조직도": site.get("유지관리조직도", ""),
            "유지관리자전체": " / ".join(
                part for part in [
                    (
                        f"{site.get('기계설비유지관리자', '')} "
                        f"({site.get('유지관리자등급', '')})"
                    ).strip()
                    if site.get("기계설비유지관리자", "")
                    else "",
                    (
                        f"{site.get('기계설비유지관리자2', '')} "
                        f"({site.get('유지관리자등급2', '')})"
                    ).strip()
                    if site.get("기계설비유지관리자2", "")
                    else "",
                ]
                if part
            ),
            "성능점검업체": COMPANY_NAME,
            "성능점검 업체": COMPANY_NAME,
            "책임기술자": responsible,
            "참여기술자": ", ".join(participants),
            "참여기술자전체": self.build_technician_summary_text(),
            "설비현황": self.build_equipment_summary_text(),
            "점검대상": self.build_target_summary_text(),
            "P13유무체크": "\n".join(
                f"{row.get('항목', '')}: {row.get('유무', '')}"
                + (
                    f" ({row.get('비고', '')})"
                    if row.get("비고", "")
                    else ""
                )
                for row in site.get("13페이지유무체크", [])
            ),
            "P18비상연락망": "\n".join(
                " / ".join(
                    value
                    for value in [
                        row.get("구분", ""),
                        row.get("기관성명", ""),
                        row.get("전화번호", ""),
                        row.get("비고", ""),
                    ]
                    if value
                )
                for row in site.get("18페이지비상연락망", [])
            ),
            **self.build_page25_values(),
        }

    @staticmethod
    def hwp_replace_all(hwp, find_text, replace_text):
        if not find_text:
            return False

        hwp.HAction.GetDefault(
            "AllReplace",
            hwp.HParameterSet.HFindReplace.HSet,
        )
        parameter = hwp.HParameterSet.HFindReplace
        parameter.FindString = str(find_text)
        parameter.ReplaceString = str(replace_text)
        parameter.IgnoreMessage = 1
        parameter.Direction = 2
        parameter.FindType = 1

        return bool(
            hwp.HAction.Execute(
                "AllReplace",
                hwp.HParameterSet.HFindReplace.HSet,
            )
        )

    @staticmethod
    def hwp_find_text(hwp, text):
        hwp.HAction.GetDefault(
            "RepeatFind",
            hwp.HParameterSet.HFindReplace.HSet,
        )
        parameter = hwp.HParameterSet.HFindReplace
        parameter.FindString = str(text)
        parameter.Direction = 0
        parameter.IgnoreMessage = 1
        parameter.FindType = 1

        return bool(
            hwp.HAction.Execute(
                "RepeatFind",
                hwp.HParameterSet.HFindReplace.HSet,
            )
        )

    def hwp_fill_next_cell_by_label(self, hwp, label, value):
        hwp.HAction.Run("MoveDocBegin")

        if not self.hwp_find_text(hwp, label):
            return False

        try:
            hwp.HAction.Run("TableRightCell")
        except Exception:
            return False

        try:
            hwp.HAction.Run("TableCellBlock")
            hwp.HAction.Run("Delete")
        except Exception:
            pass

        self.hwp_insert_text(hwp, str(value))
        return True

    def create_mapping_template(self):
        original_text = self.original_sample_path.text().strip()

        if not original_text or not Path(original_text).exists():
            QMessageBox.warning(
                self,
                "완성본 원본 확인",
                "완성본 참고용 HWP를 먼저 선택하십시오.",
            )
            return

        output_folder = Path(__file__).resolve().parent / "templates"
        output_folder.mkdir(parents=True, exist_ok=True)
        mapped_path = output_folder / "기계설비성능점검_자동화매핑템플릿.hwp"

        try:
            shutil.copy2(Path(original_text), mapped_path)
        except OSError as error:
            QMessageBox.critical(
                self,
                "매핑템플릿 복사 실패",
                str(error),
            )
            return

        try:
            import win32com.client
        except ImportError:
            QMessageBox.critical(
                self,
                "한글 자동화 모듈 없음",
                "pywin32가 설치되어 있지 않습니다.",
            )
            return

        hwp = None

        # 완성본에 실제로 들어 있던 가변값을 긴 문자열부터 표식으로 바꾼다.
        sample_to_placeholder = [
            # 표지 및 제출문: 긴 문구부터 처리하여 글상자·문단 서식을 보존
            ("테스트센터 기계설비 성능점검 계획 및 성능점검 결과 보고서",
             "{{현장명}} 기계설비 성능점검 계획 및 성능점검 결과 보고서"),
            ("테스트센터 기계설비 성능점검 계획 및 결과보고서",
             "{{현장명}} 기계설비 성능점검 계획 및 결과보고서"),
            ("테스트센터 기계설비 성능점검 결과보고서",
             "{{현장명}} 기계설비 성능점검 결과보고서"),
            ("테스트센터 귀중", "{{현장명}} 귀중"),
            ("테스트센터", "{{현장명}}"),

            # 제출일·작성일: 연도 또는 월만 따로 바꾸지 않아 목차 깨짐 방지
            ("2099년 01월 31일", "{{작성일한글}}"),
            ("2099년 1월 31일", "{{작성일한글}}"),
            ("2099. 01. 31.", "{{작성일점}}"),
            ("2099.01.31.", "{{작성일점}}"),
            ("2099년 01월", "{{작성년월}}"),
            ("2099년 1월", "{{작성년월}}"),

            # 점검기간
            ("2099년 01월 01일 ~ 2099년 01월 31일", "{{점검기간}}"),
            ("2099년 1월 1일 ~ 2099년 1월 31일", "{{점검기간}}"),
            ("2099. 01. 01. ~ 2099. 01. 31.", "{{점검기간}}"),
            ("2099년 01월 01일", "{{점검시작일}}"),
            ("2099년 1월 1일", "{{점검시작일}}"),
            ("2099. 01. 01.", "{{점검시작일점}}"),

            # 성능점검 기준일
            ("2098년 01월 01일", "{{성능점검기준일한글}}"),
            ("2098년 1월 1일", "{{성능점검기준일한글}}"),
            ("2098. 01. 01.", "{{성능점검기준일점}}"),

            # 건축물 정보
            ("서울특별시 예시구 예시로 00 테스트센터", "{{주소}}"),
            ("서울특별시 예시구 예시로 00", "{{주소}}"),
            ("1,234.56㎡", "{{연면적}}㎡"),
            ("1,234.56", "{{연면적}}"),
            ("테스트관리주체", "{{관리주체}}"),
            ("02-0000-0000", "{{전화번호}}"),

            # 유지관리자 2명 지원
            ("테스트유지관리자1", "{{기계설비유지관리자1}}"),

            # 7·12·13·18·25페이지 추가 입력 표식
            ("{{관리주체주소}}", "{{관리주체주소}}"),
            ("{{유지관리자1선임일}}", "{{유지관리자1선임일}}"),
            ("{{유지관리자1교육수료일}}", "{{유지관리자1교육수료일}}"),
            ("{{유지관리자2선임일}}", "{{유지관리자2선임일}}"),
            ("{{유지관리자2교육수료일}}", "{{유지관리자2교육수료일}}"),
            ("{{유지관리조직도}}", "{{유지관리조직도}}"),
            ("{{P13유무체크}}", "{{P13유무체크}}"),
            ("{{P18비상연락망}}", "{{P18비상연락망}}"),

            # 성능점검 기술자
            ("테스트책임자", "{{책임기술자}}"),
            ("테스트참여자1", "{{참여기술자1}}"),
            ("테스트참여자2", "{{참여기술자2}}"),
            ("테스트참여자3", "{{참여기술자3}}"),
            ("테스트참여자4", "{{참여기술자4}}"),
        ]

        try:
            hwp = win32com.client.Dispatch(
                "HWPFrame.HwpObject"
            )
            hwp.XHwpWindows.Item(0).Visible = True

            opened = hwp.Open(str(mapped_path))

            if opened is False:
                raise RuntimeError(
                    "복사한 완성본 HWP를 열지 못했습니다."
                )

            audit = []

            for old_text, placeholder in sample_to_placeholder:
                changed = self.hwp_replace_all(
                    hwp,
                    old_text,
                    placeholder,
                )
                audit.append(
                    f"{old_text} -> {placeholder} : "
                    f"{'처리' if changed else '문구없음'}"
                )

            hwp.SaveAs(str(mapped_path), "HWP", "")

            audit_path = output_folder / (
                "기계설비성능점검_매핑템플릿_생성내역.txt"
            )
            audit_path.write_text(
                "\n".join(audit),
                encoding="utf-8",
            )

            self.report_template_path.setText(str(mapped_path))

            QMessageBox.information(
                self,
                "매핑템플릿 생성 완료",
                "완성본 1~27쪽의 현장별 가변값을 정밀 표식으로 바꾼 "
                "자동화 매핑템플릿을 생성했습니다.\n\n"
                f"{mapped_path}\n\n"
                "첫 장 현장명·날짜와 2쪽 현장명도 전역 표식으로 변환했습니다.",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "매핑템플릿 생성 실패",
                str(error),
            )

        finally:
            if hwp is not None:
                try:
                    hwp.Quit()
                except Exception:
                    pass

    def hwp_replace_first(self, hwp, find_text, replace_text):
        hwp.HAction.Run("MoveDocBegin")

        if not self.hwp_find_text(hwp, find_text):
            return False

        try:
            hwp.HAction.Run("Select")
            self.hwp_insert_text(hwp, str(replace_text))
            return True
        except Exception:
            return False

    def hwp_set_relative_table_cell(
        self,
        hwp,
        anchor_text,
        move_count,
        value,
    ):
        hwp.HAction.Run("MoveDocBegin")

        if not self.hwp_find_text(hwp, anchor_text):
            return False

        try:
            for _ in range(move_count):
                hwp.HAction.Run("TableRightCell")

            hwp.HAction.Run("TableCellBlock")
            hwp.HAction.Run("Delete")
            self.hwp_insert_text(hwp, str(value))
            return True
        except Exception:
            return False

    def fill_page7_direct(self, hwp, values, audit):
        replacements = [
            ("(건축물명 : 테스트센터)",
             f"(건축물명 : {values.get('현장명', '')})"),
            ("2099. 01. .", values.get("작성년월점", "")),
            ("테스트관리주체", values.get("관리주체", "")),
            ("테스트유지관리자1", values.get("기계설비유지관리자1", "")),
            ("테스트유지관리자2", values.get("기계설비유지관리자2", "")),
        ]

        for old, new in replacements:
            changed = self.hwp_replace_all(hwp, old, new)
            audit.append(
                {
                    "항목": f"7페이지:{old}",
                    "방식": "직접치환",
                    "결과": "처리" if changed else "문구없음",
                    "값": str(new),
                }
            )

    def fill_page12_direct(self, hwp, values, audit):
        direct_replacements = [
            ("문화및집회시설", values.get("용도", "")),
            ("테스트유지관리자1\n(특급)",
             f"{values.get('기계설비유지관리자1', '')}\n"
             f"({values.get('유지관리자등급1', '')})"),
            ("서울특별시 예시구 예시로 00 테스트센터",
             values.get("관리주체주소", "")),
            ("2099.01.01", values.get("유지관리자1선임일", "")),
            ("2099.01.02", values.get("유지관리자1교육수료일", "")),
            ("2099.01.03", values.get("유지관리자2선임일", "")),
            ("2099.01.04", values.get("유지관리자2교육수료일", "")),
            ("테스트유지관리자2", values.get("기계설비유지관리자2", "")),
            ("초급", values.get("유지관리자등급2", "")),
        ]

        for old, new in direct_replacements:
            changed = self.hwp_replace_all(hwp, old, new)
            audit.append(
                {
                    "항목": f"12페이지:{old}",
                    "방식": "직접치환",
                    "결과": "처리" if changed else "문구없음",
                    "값": str(new),
                }
            )

        # 유지관리자 2가 없으면 관련 기존 값 전부 공란화
        if not values.get("기계설비유지관리자2", ""):
            for old in ["테스트유지관리자2", "초급", "2099.01.03", "2099.01.04"]:
                self.hwp_replace_all(hwp, old, "")

    def fill_page13_direct(self, hwp, audit):
        for row in self.collect_page13_data():
            item_name = row.get("항목", "").strip()
            status = row.get("유무", "").strip()

            if not item_name:
                continue

            symbol = {
                "유": "○",
                "무": "×",
                "해당없음": "/",
            }.get(status, status)

            changed = self.hwp_set_relative_table_cell(
                hwp,
                item_name,
                1,
                symbol,
            )
            audit.append(
                {
                    "항목": f"13페이지:{item_name}",
                    "방식": "항목우측셀",
                    "결과": "입력" if changed else "항목미확인",
                    "값": symbol,
                }
            )

    def fill_page18_direct(self, hwp, audit):
        for row in self.collect_emergency_data():
            anchor = (
                row.get("기관성명", "").strip()
                or row.get("구분", "").strip()
            )
            phone = row.get("전화번호", "").strip()

            if not anchor or not phone:
                continue

            changed = self.hwp_set_relative_table_cell(
                hwp,
                anchor,
                1,
                phone,
            )

            # 표 셀 이동이 안 되는 개체형 표는 기존 전화번호 표식 치환을 보조로 사용
            if not changed:
                changed = self.hwp_replace_all(
                    hwp,
                    f"{{{{P18_{anchor}_전화번호}}}}",
                    phone,
                )

            audit.append(
                {
                    "항목": f"18페이지:{anchor}",
                    "방식": "비상연락망셀",
                    "결과": "입력" if changed else "항목미확인",
                    "값": phone,
                }
            )

    def fill_page25_direct(self, hwp, audit):
        for item in self.collect_equipment_data():
            equipment_name = item.get("설비명", "").strip()

            if not equipment_name:
                continue

            selected = bool(item.get("선택"))
            target_symbol = "○" if selected else "-"
            total_value = (
                str(item.get("전체수량", 0))
                if selected
                else "-"
            )
            inspection_value = (
                str(item.get("점검수량", 0))
                if selected
                else "-"
            )

            # 25페이지 표 구조:
            # 설비명 → 대상여부 → 전체수량 → (중간 점검수량/공란) → 산출기준 → 최종 점검수량
            result_target = self.hwp_set_relative_table_cell(
                hwp, equipment_name, 1, target_symbol
            )
            result_total = self.hwp_set_relative_table_cell(
                hwp, equipment_name, 2, total_value
            )

            # 템플릿별 열 차이를 고려하여 3열과 5열 모두 시도
            result_inspection_3 = self.hwp_set_relative_table_cell(
                hwp, equipment_name, 3, inspection_value
            )
            result_inspection_5 = self.hwp_set_relative_table_cell(
                hwp, equipment_name, 5, inspection_value
            )

            audit.append(
                {
                    "항목": f"25페이지:{equipment_name}",
                    "방식": "설비명기준 셀이동",
                    "결과": (
                        "입력"
                        if (
                            result_target
                            and result_total
                            and (
                                result_inspection_3
                                or result_inspection_5
                            )
                        )
                        else "표구조확인필요"
                    ),
                    "값": (
                        f"{target_symbol} / "
                        f"{total_value} / "
                        f"{inspection_value}"
                    ),
                }
            )

    def fill_front_27_pages(self, hwp):
        values = self.build_front_page_values()

        participant_names = []

        for item in self.collect_technician_data():
            name = item.get("성명", "").strip()

            if (
                name
                and item.get("구분") != "책임기술자"
            ):
                participant_names.append(name)

        participant_names += ["", "", "", ""]
        values["참여기술자1"] = participant_names[0]
        values["참여기술자2"] = participant_names[1]
        values["참여기술자3"] = participant_names[2]
        values["참여기술자4"] = participant_names[3]

        audit = []

        # 1차: 템플릿에 사용자가 넣어둔 {{항목명}} 표식 치환
        for key, value in values.items():
            placeholder = "{{" + key + "}}"

            try:
                changed = self.hwp_replace_all(
                    hwp,
                    placeholder,
                    value,
                )
                audit.append(
                    {
                        "항목": key,
                        "방식": "표식치환",
                        "결과": "처리" if changed else "표식없음",
                        "값": str(value),
                    }
                )
            except Exception as error:
                audit.append(
                    {
                        "항목": key,
                        "방식": "표식치환",
                        "결과": f"오류: {error}",
                        "값": str(value),
                    }
                )

        # 2차: 빈 표 셀은 왼쪽 라벨을 찾아 오른쪽 셀에 입력
        label_aliases = {
            "현장명": ["현장명", "건축물명", "건축물 명"],
            "주소": ["주소", "소재지"],
            "연면적": ["연면적"],
            "건축물용도": ["건축물 용도", "주용도", "용도"],
            "세대수": ["세대수"],
            "층수": ["층수"],
            "준공일": ["준공일", "사용승인일"],
            "성능점검기준일": [
                "성능점검 기준일",
                "성능점검기준일",
            ],
            "점검기간": ["점검기간", "성능점검 기간"],
            "관리주체": ["관리주체"],
            "대표자": ["대표자", "대표자·담당자"],
            "전화번호": ["전화번호", "연락처"],
            "기계설비유지관리자": [
                "기계설비 유지관리자",
                "기계설비유지관리자",
                "유지관리자",
                "유지관리자 1",
            ],
            "유지관리자등급": [
                "유지관리자 등급",
                "유지관리자 1 등급",
                "등급",
            ],
            "기계설비유지관리자2": [
                "기계설비 유지관리자 2",
                "기계설비유지관리자 2",
                "유지관리자 2",
            ],
            "유지관리자등급2": [
                "유지관리자 2 등급",
                "등급 2",
            ],
            "성능점검업체": [
                "성능점검업체",
                "성능점검 업체",
                "성능점검 대행업체",
            ],
            "책임기술자": ["책임기술자"],
            "참여기술자": ["참여기술자"],
            "보고서작성일": ["보고서 작성일", "작성일"],
            "설비현황": ["설비현황", "기계설비 현황"],
            "점검대상": ["점검대상", "성능점검 대상"],
        }

        for key, labels in label_aliases.items():
            value = values.get(key, "")

            if value in (None, ""):
                continue

            inserted = False

            for label in labels:
                try:
                    if self.hwp_fill_next_cell_by_label(
                        hwp,
                        label,
                        value,
                    ):
                        audit.append(
                            {
                                "항목": key,
                                "방식": f"라벨셀({label})",
                                "결과": "입력",
                                "값": str(value),
                            }
                        )
                        inserted = True
                        break
                except Exception as error:
                    audit.append(
                        {
                            "항목": key,
                            "방식": f"라벨셀({label})",
                            "결과": f"오류: {error}",
                            "값": str(value),
                        }
                    )

            if not inserted:
                audit.append(
                    {
                        "항목": key,
                        "방식": "라벨셀",
                        "결과": "대상 라벨 미확인",
                        "값": str(value),
                    }
                )

        # 표식 치환 후 페이지별 실제 표·문구에 직접 입력
        self.fill_page7_direct(hwp, values, audit)
        self.fill_page12_direct(hwp, values, audit)
        self.fill_page13_direct(hwp, audit)
        self.fill_page18_direct(hwp, audit)
        self.fill_page25_direct(hwp, audit)

        return audit

    @staticmethod
    def write_template_audit(path, audit):
        lines = [
            "자동화템플릿 입력 결과",
            "=" * 50,
            "",
        ]

        for item in audit:
            lines.append(
                f"[{item.get('항목', '')}] "
                f"{item.get('방식', '직접치환')} / "
                f"{item.get('결과', '')} / "
                f"입력값: {item.get('값', '')} / "
                f"건수: {item.get('건수', '')}"
            )

        Path(path).write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

    @staticmethod
    def xml_local_name(tag):
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    @staticmethod
    def normalize_hwp_text(text):
        return (
            str(text or "")
            .replace("\u00a0", " ")
            .replace("\u3000", " ")
            .replace("\r", "")
            .strip()
        )

    def hwpml_text_nodes(self, root):
        nodes = []

        for element in root.iter():
            if element.text is None:
                continue

            text = self.normalize_hwp_text(element.text)

            if text:
                nodes.append(element)

        return nodes

    def hwpml_replace_all(self, root, old_text, new_text):
        old_norm = self.normalize_hwp_text(old_text)

        if not old_norm:
            return 0

        count = 0

        for element in root.iter():
            if element.text is None:
                continue

            current = self.normalize_hwp_text(element.text)

            if old_norm in current:
                element.text = element.text.replace(
                    old_text,
                    str(new_text),
                )
                count += 1

        return count

    def hwpml_replace_placeholder_values(self, root, values):
        result = []

        for key, value in values.items():
            placeholder = "{{" + key + "}}"
            count = self.hwpml_replace_all(
                root,
                placeholder,
                value,
            )
            result.append(
                {
                    "항목": key,
                    "방식": "HWPML 표식치환",
                    "결과": "처리" if count else "표식없음",
                    "값": str(value),
                    "건수": count,
                }
            )

        return result

    def hwpml_find_anchor_indexes(self, nodes, anchor):
        anchor_norm = self.normalize_hwp_text(anchor)
        indexes = []

        for index, element in enumerate(nodes):
            text = self.normalize_hwp_text(element.text)

            if anchor_norm and anchor_norm in text:
                indexes.append(index)

        return indexes

    def hwpml_replace_next_value(
        self,
        nodes,
        anchor,
        value,
        max_scan=30,
        skip_texts=None,
        occurrence=0,
    ):
        skip_texts = {
            self.normalize_hwp_text(item)
            for item in (skip_texts or [])
        }
        indexes = self.hwpml_find_anchor_indexes(nodes, anchor)

        if len(indexes) <= occurrence:
            return False, "앵커없음"

        start = indexes[occurrence]

        for index in range(
            start + 1,
            min(len(nodes), start + 1 + max_scan),
        ):
            element = nodes[index]
            text = self.normalize_hwp_text(element.text)

            if not text:
                continue

            if text in skip_texts:
                continue

            # 다음 항목 라벨로 판단되는 긴 문장은 건너뛴다.
            if len(text) > 45 and not any(
                ch.isdigit() for ch in text
            ):
                continue

            element.text = str(value)
            return True, text

        return False, "후속값없음"

    def hwpml_replace_exact_or_near(
        self,
        root,
        nodes,
        exact_candidates,
        anchor_candidates,
        value,
        audit_name,
    ):
        total = 0

        for candidate in exact_candidates:
            total += self.hwpml_replace_all(
                root,
                candidate,
                value,
            )

        if total:
            return {
                "항목": audit_name,
                "방식": "HWPML 기존값치환",
                "결과": "입력",
                "값": str(value),
                "건수": total,
            }

        for anchor in anchor_candidates:
            changed, previous = self.hwpml_replace_next_value(
                nodes,
                anchor,
                value,
            )

            if changed:
                return {
                    "항목": audit_name,
                    "방식": f"HWPML 앵커셀({anchor})",
                    "결과": "입력",
                    "값": str(value),
                    "건수": 1,
                    "기존값": previous,
                }

        return {
            "항목": audit_name,
            "방식": "HWPML",
            "결과": "위치미확인",
            "값": str(value),
            "건수": 0,
        }

    def apply_hwpml_page_mapping(self, hwp, audit_path):
        xml_text = hwp.GetTextFile("HWPML2X", "")

        if not xml_text:
            raise RuntimeError(
                "한글 문서에서 HWPML2X 데이터를 읽지 못했습니다."
            )

        root = ET.fromstring(xml_text)
        nodes = self.hwpml_text_nodes(root)
        values = self.build_front_page_values()
        audit = self.hwpml_replace_placeholder_values(
            root,
            values,
        )

        # 7페이지
        page7_map = [
            (
                ["테스트센터"],
                ["건축물명", "현장명"],
                values.get("현장명", ""),
                "7페이지 현장명",
            ),
            (
                ["2026. 07.", "2026년 07월"],
                ["작성일", "점검일자"],
                values.get("작성년월점", ""),
                "7페이지 점검일자",
            ),
            (
                ["테스트관리주체"],
                ["관리주체"],
                values.get("관리주체", ""),
                "7페이지 관리주체",
            ),
            (
                ["테스트유지관리자1"],
                ["유지관리자", "선임인"],
                values.get("기계설비유지관리자1", ""),
                "7페이지 유지관리자1",
            ),
            (
                ["테스트유지관리자2"],
                ["보조 유지관리자", "유지관리자 2"],
                values.get("기계설비유지관리자2", ""),
                "7페이지 유지관리자2",
            ),
        ]

        for exacts, anchors, value, name in page7_map:
            audit.append(
                self.hwpml_replace_exact_or_near(
                    root,
                    nodes,
                    exacts,
                    anchors,
                    value,
                    name,
                )
            )

        # 12페이지
        page12_map = [
            (
                ["문화및집회시설", "문화 및 집회시설"],
                ["용도", "주용도"],
                values.get("용도", ""),
                "12페이지 용도",
            ),
            (
                [],
                ["관리주체 주소", "주소"],
                values.get("관리주체주소", ""),
                "12페이지 관리주체 주소",
            ),
            (
                ["특급"],
                ["선임인 등급", "유지관리자 등급"],
                values.get("유지관리자등급1", ""),
                "12페이지 유지관리자1 등급",
            ),
            (
                ["2023.08.09", "2023. 08. 09."],
                ["선임일"],
                values.get("유지관리자1선임일", ""),
                "12페이지 유지관리자1 선임일",
            ),
            (
                ["2023.10.03", "2023. 10. 03."],
                ["교육수료일"],
                values.get("유지관리자1교육수료일", ""),
                "12페이지 유지관리자1 교육수료일",
            ),
            (
                ["초급"],
                ["보조자 등급", "유지관리자 2 등급"],
                values.get("유지관리자등급2", ""),
                "12페이지 유지관리자2 등급",
            ),
            (
                ["2026.06.26", "2026. 06. 26."],
                ["선임일"],
                values.get("유지관리자2선임일", ""),
                "12페이지 유지관리자2 선임일",
            ),
            (
                ["2026.07.00", "2026. 07. 00."],
                ["교육수료일"],
                values.get("유지관리자2교육수료일", ""),
                "12페이지 유지관리자2 교육수료일",
            ),
        ]

        for exacts, anchors, value, name in page12_map:
            audit.append(
                self.hwpml_replace_exact_or_near(
                    root,
                    nodes,
                    exacts,
                    anchors,
                    value,
                    name,
                )
            )

        # 조직도는 표식 우선, 없으면 조직도 제목 다음 값을 교체
        org_value = values.get("유지관리조직도", "")
        if org_value:
            audit.append(
                self.hwpml_replace_exact_or_near(
                    root,
                    nodes,
                    [],
                    ["기계설비 유지관리 조직도", "유지관리 조직도"],
                    org_value,
                    "12페이지 유지관리 조직도",
                )
            )

        # 13페이지 유무 체크
        for row in self.collect_page13_data():
            item_name = row.get("항목", "").strip()
            status = row.get("유무", "").strip()

            if not item_name:
                continue

            symbol = {
                "유": "○",
                "무": "×",
                "해당없음": "/",
            }.get(status, status)

            changed, previous = self.hwpml_replace_next_value(
                nodes,
                item_name,
                symbol,
                max_scan=12,
                skip_texts=[
                    "유",
                    "무",
                    "해당없음",
                    "비고",
                ],
            )
            audit.append(
                {
                    "항목": f"13페이지 {item_name}",
                    "방식": "HWPML 항목 인접값",
                    "결과": "입력" if changed else "위치미확인",
                    "값": symbol,
                    "기존값": previous,
                }
            )

        # 18페이지 비상연락망
        for row in self.collect_emergency_data():
            anchor = (
                row.get("기관성명", "").strip()
                or row.get("구분", "").strip()
            )
            phone = row.get("전화번호", "").strip()

            if not anchor or not phone:
                continue

            changed, previous = self.hwpml_replace_next_value(
                nodes,
                anchor,
                phone,
                max_scan=15,
                skip_texts=["전화번호", "연락처", "비고"],
            )
            audit.append(
                {
                    "항목": f"18페이지 {anchor}",
                    "방식": "HWPML 비상연락망 인접값",
                    "결과": "입력" if changed else "위치미확인",
                    "값": phone,
                    "기존값": previous,
                }
            )

        # 25페이지 설비별 대상여부·전체수량·점검수량
        for item in self.collect_equipment_data():
            equipment_name = item.get("설비명", "").strip()

            if not equipment_name:
                continue

            selected = bool(item.get("선택"))
            values_to_write = [
                "○" if selected else "-",
                str(item.get("전체수량", 0)) if selected else "-",
                str(item.get("점검수량", 0)) if selected else "-",
            ]

            anchor_indexes = self.hwpml_find_anchor_indexes(
                nodes,
                equipment_name,
            )

            if not anchor_indexes:
                audit.append(
                    {
                        "항목": f"25페이지 {equipment_name}",
                        "방식": "HWPML 설비행",
                        "결과": "설비명미확인",
                        "값": " / ".join(values_to_write),
                    }
                )
                continue

            start = anchor_indexes[0]
            written = 0
            cursor = start + 1

            while (
                cursor < len(nodes)
                and written < len(values_to_write)
                and cursor <= start + 30
            ):
                text = self.normalize_hwp_text(
                    nodes[cursor].text
                )

                if not text:
                    cursor += 1
                    continue

                # 다음 설비명 또는 설명문은 건너뛴다.
                if len(text) > 30 and not any(
                    ch.isdigit() for ch in text
                ):
                    cursor += 1
                    continue

                nodes[cursor].text = values_to_write[written]
                written += 1
                cursor += 1

            audit.append(
                {
                    "항목": f"25페이지 {equipment_name}",
                    "방식": "HWPML 설비행 순차입력",
                    "결과": (
                        "입력"
                        if written == 3
                        else f"부분입력({written}/3)"
                    ),
                    "값": " / ".join(values_to_write),
                }
            )

        output_xml = ET.tostring(
            root,
            encoding="unicode",
        )

        set_result = hwp.SetTextFile(
            output_xml,
            "HWPML2X",
            "",
        )

        if set_result is False:
            raise RuntimeError(
                "수정한 HWPML2X 데이터를 한글 문서에 적용하지 못했습니다."
            )

        # 진단용 주변 텍스트 기록
        lines = [
            "HWPML 셀매핑 결과",
            "=" * 60,
            "",
        ]

        for item in audit:
            lines.append(
                f"[{item.get('항목', '')}] "
                f"{item.get('방식', '')} / "
                f"{item.get('결과', '')} / "
                f"값={item.get('값', '')}"
            )

        lines.extend(
            [
                "",
                "문서 텍스트 앞부분 진단",
                "-" * 60,
            ]
        )

        for index, element in enumerate(nodes[:500]):
            lines.append(
                f"{index:04d}: "
                f"{self.normalize_hwp_text(element.text)}"
            )

        Path(audit_path).write_text(
            "\n".join(lines),
            encoding="utf-8",
        )

        return audit

    @staticmethod
    def xml_path_map(root):
        path_map = {}

        def walk(element, path):
            path_map[path] = element
            for index, child in enumerate(list(element)):
                walk(child, path + (index,))

        walk(root, ())
        return path_map

    def xml_text_paths(self, root):
        result = []

        def walk(element, path):
            if element.text is not None:
                text = self.normalize_hwp_text(element.text)
                if text:
                    result.append((path, element, text))

            for index, child in enumerate(list(element)):
                walk(child, path + (index,))

        walk(root, ())
        return result

    def find_original_paths(self, original_entries, candidates):
        normalized = [
            self.normalize_hwp_text(candidate)
            for candidate in candidates
            if candidate
        ]
        matches = []

        for path, element, text in original_entries:
            for candidate in normalized:
                if candidate and candidate in text:
                    matches.append((path, element, text, candidate))
                    break

        return matches

    @staticmethod
    def is_phone_text(text):
        digits = "".join(ch for ch in str(text) if ch.isdigit())
        return (
            len(digits) >= 8
            and any(mark in str(text) for mark in ["-", ")", " "])
        )

    @staticmethod
    def is_short_value_text(text):
        value = str(text).strip()

        if not value:
            return False

        if len(value) > 30:
            return False

        return True

    def set_target_at_original_path(
        self,
        target_path_map,
        path,
        value,
    ):
        target = target_path_map.get(path)

        if target is None:
            return False

        target.text = str(value)
        return True

    def set_by_original_text_paths(
        self,
        original_entries,
        target_path_map,
        candidates,
        value,
        audit_name,
        all_occurrences=True,
    ):
        matches = self.find_original_paths(
            original_entries,
            candidates,
        )

        if not matches:
            return {
                "항목": audit_name,
                "결과": "원본값미확인",
                "값": str(value),
                "건수": 0,
            }

        changed = 0

        for path, _, _, _ in matches:
            if self.set_target_at_original_path(
                target_path_map,
                path,
                value,
            ):
                changed += 1

            if not all_occurrences:
                break

        return {
            "항목": audit_name,
            "결과": "입력" if changed else "대상경로없음",
            "값": str(value),
            "건수": changed,
        }

    def find_nearby_value_path(
        self,
        original_entries,
        anchor_path,
        validator=None,
        max_scan=25,
        occurrence_offset=0,
    ):
        indexes = [
            index
            for index, (path, _, _) in enumerate(original_entries)
            if path == anchor_path
        ]

        if not indexes:
            return None, None

        start_index = indexes[0] + 1 + occurrence_offset

        for index in range(
            start_index,
            min(len(original_entries), start_index + max_scan),
        ):
            path, _, text = original_entries[index]

            if validator is not None and not validator(text):
                continue

            if validator is None and not self.is_short_value_text(text):
                continue

            return path, text

        return None, None

    def build_page7_replacements(self):
        values = self.build_front_page_values()
        manager2 = values.get("기계설비유지관리자2", "")

        return [
            ("{{현장명}}", values.get("현장명", "")),
            ("{{ 현장명 }}", values.get("현장명", "")),
            ("{{건축물명}}", values.get("현장명", "")),
            ("{{관리주체}}", values.get("관리주체", "")),
            ("{{ 관리주체 }}", values.get("관리주체", "")),
            ("{{기계설비유지관리자1}}", values.get("기계설비유지관리자1", "")),
            ("{{기계설비유지 관리자1}}", values.get("기계설비유지관리자1", "")),
            ("{{기계설비유지\n관리자1}}", values.get("기계설비유지관리자1", "")),
            ("{{ 기계설비유지관리자1 }}", values.get("기계설비유지관리자1", "")),
            ("{{기계설비유지관리자2}}", manager2),
            ("{{기계설비유지 관리자2}}", manager2),
            ("{{기계설비유지\n관리자2}}", manager2),
            ("테스트유지관리자2", manager2),
            ("{{점검일자}}", values.get("작성일점", "")),
            ("{{작성일점}}", values.get("작성일점", "")),
            ("{{작성년월점}}", values.get("작성년월점", "")),
            ("2026.   07.     .", values.get("작성일점", "")),
            ("2026.  07.    .", values.get("작성일점", "")),
            ("2026. 07.   .", values.get("작성일점", "")),
            ("2026. 07.  .", values.get("작성일점", "")),
            ("2026. 07. .", values.get("작성일점", "")),
            ("2026.   07.", values.get("작성년월점", "")),
            ("2026.  07.", values.get("작성년월점", "")),
            ("2026. 07.", values.get("작성년월점", "")),
        ]

    def apply_page7_direct_replacements(self, hwp, audit):
        for old_text, new_text in self.build_page7_replacements():
            try:
                changed = self.hwp_replace_all(hwp, old_text, new_text)
            except Exception:
                changed = False

            audit.append(
                {
                    "항목": f"7페이지:{old_text}",
                    "방식": "직접치환",
                    "결과": "입력" if changed else "문구없음",
                    "값": str(new_text),
                    "건수": 1 if changed else 0,
                }
            )

        return audit

    def apply_original_structure_mapping(
        self,
        target_hwp,
        original_path,
        audit_path,
    ):
        import win32com.client

        original_hwp = None

        try:
            original_hwp = win32com.client.DispatchEx(
                "HWPFrame.HwpObject"
            )
            original_hwp.XHwpWindows.Item(0).Visible = False

            if original_hwp.Open(str(original_path)) is False:
                raise RuntimeError(
                    "원본보존 HWP를 열지 못했습니다."
                )

            original_xml = original_hwp.GetTextFile(
                "HWPML2X",
                "",
            )
            target_xml = target_hwp.GetTextFile(
                "HWPML2X",
                "",
            )

            if not original_xml or not target_xml:
                raise RuntimeError(
                    "원본 또는 자동화템플릿의 HWPML 구조를 읽지 못했습니다."
                )

            original_root = ET.fromstring(original_xml)
            target_root = ET.fromstring(target_xml)

            original_entries = self.xml_text_paths(
                original_root
            )
            target_path_map = self.xml_path_map(
                target_root
            )

            values = self.build_front_page_values()
            audit = []

            # 겉표지~7페이지 반복값: 원본 위치를 그대로 사용
            fixed_map = [
                (
                    ["테스트센터"],
                    values.get("현장명", ""),
                    "현장명 전체",
                    True,
                ),
                (
                    ["2026년 07월 30일", "2026. 07. 30."],
                    values.get("작성일한글", ""),
                    "제출일·작성일",
                    True,
                ),
                (
                    ["2026년 07월", "2026. 07."],
                    values.get("작성년월", ""),
                    "작성년월",
                    True,
                ),
                (
                    ["테스트관리주체"],
                    values.get("관리주체", ""),
                    "관리주체",
                    True,
                ),
                (
                    [
                        "서울특별시 예시구 예시로 00",
                        "예시구 예시로 00",
                    ],
                    values.get("관리주체주소", "")
                    or values.get("주소", ""),
                    "관리주체 주소",
                    True,
                ),
                (
                    ["문화및집회시설", "문화 및 집회시설"],
                    values.get("용도", ""),
                    "12페이지 용도",
                    True,
                ),
                (
                    ["테스트유지관리자1"],
                    values.get("기계설비유지관리자1", ""),
                    "유지관리자1",
                    True,
                ),
                (
                    ["테스트유지관리자2"],
                    values.get("기계설비유지관리자2", ""),
                    "유지관리자2",
                    True,
                ),
                (
                    ["2023.08.09", "2023. 08. 09."],
                    values.get("유지관리자1선임일", ""),
                    "유지관리자1 선임일",
                    True,
                ),
                (
                    ["2023.10.03", "2023. 10. 03."],
                    values.get("유지관리자1교육수료일", ""),
                    "유지관리자1 교육수료일",
                    True,
                ),
                (
                    ["2026.06.26", "2026. 06. 26."],
                    values.get("유지관리자2선임일", ""),
                    "유지관리자2 선임일",
                    True,
                ),
                (
                    ["2026.07.00", "2026. 07. 00."],
                    values.get("유지관리자2교육수료일", ""),
                    "유지관리자2 교육수료일",
                    True,
                ),
            ]

            for candidates, value, name, all_occurrences in fixed_map:
                audit.append(
                    self.set_by_original_text_paths(
                        original_entries,
                        target_path_map,
                        candidates,
                        value,
                        name,
                        all_occurrences,
                    )
                )

            # 12페이지 등급은 이름 주변의 원본 등급 위치를 찾아 같은 경로에 입력
            for manager_name, grade_value, audit_name in [
                (
                    "테스트유지관리자1",
                    values.get("유지관리자등급1", ""),
                    "유지관리자1 등급",
                ),
                (
                    "테스트유지관리자2",
                    values.get("유지관리자등급2", ""),
                    "유지관리자2 등급",
                ),
            ]:
                manager_matches = self.find_original_paths(
                    original_entries,
                    [manager_name],
                )

                changed = False

                for anchor_path, _, _, _ in manager_matches:
                    value_path, old_value = self.find_nearby_value_path(
                        original_entries,
                        anchor_path,
                        validator=lambda text: text in [
                            "특급",
                            "고급",
                            "중급",
                            "초급",
                            "보조",
                        ],
                        max_scan=12,
                    )

                    if value_path and self.set_target_at_original_path(
                        target_path_map,
                        value_path,
                        grade_value,
                    ):
                        changed = True
                        break

                audit.append(
                    {
                        "항목": audit_name,
                        "결과": "입력" if changed else "위치미확인",
                        "값": grade_value,
                        "건수": 1 if changed else 0,
                    }
                )

            # 유지관리자2가 없으면 원본의 관련 위치를 모두 공란 처리
            if not values.get("기계설비유지관리자2", ""):
                for candidates, name in [
                    (["테스트유지관리자2"], "유지관리자2 성명 공란"),
                    (["2026.06.26", "2026. 06. 26."], "유지관리자2 선임일 공란"),
                    (["2026.07.00", "2026. 07. 00."], "유지관리자2 교육일 공란"),
                ]:
                    audit.append(
                        self.set_by_original_text_paths(
                            original_entries,
                            target_path_map,
                            candidates,
                            "",
                            name,
                            True,
                        )
                    )

            # 13페이지 유무 체크: 원본 항목명 위치 뒤의 기존 유/무 표시 경로를 사용
            for row in self.collect_page13_data():
                item_name = row.get("항목", "").strip()
                status = row.get("유무", "").strip()

                if not item_name:
                    continue

                symbol = {
                    "유": "○",
                    "무": "×",
                    "해당없음": "/",
                }.get(status, status)

                item_matches = self.find_original_paths(
                    original_entries,
                    [item_name],
                )
                changed = False

                for item_path, _, _, _ in item_matches:
                    value_path, old_value = self.find_nearby_value_path(
                        original_entries,
                        item_path,
                        validator=lambda text: text in [
                            "○",
                            "×",
                            "유",
                            "무",
                            "/",
                            "-",
                        ],
                        max_scan=20,
                    )

                    if value_path and self.set_target_at_original_path(
                        target_path_map,
                        value_path,
                        symbol,
                    ):
                        changed = True
                        break

                audit.append(
                    {
                        "항목": f"13페이지 {item_name}",
                        "결과": "입력" if changed else "위치미확인",
                        "값": symbol,
                        "건수": 1 if changed else 0,
                    }
                )

            # 18페이지 비상연락망: 원본 기관명 뒤의 전화번호 경로를 그대로 사용
            for row in self.collect_emergency_data():
                anchor = (
                    row.get("기관성명", "").strip()
                    or row.get("구분", "").strip()
                )
                phone = row.get("전화번호", "").strip()

                if not anchor or not phone:
                    continue

                anchor_matches = self.find_original_paths(
                    original_entries,
                    [anchor],
                )
                changed = False

                for anchor_path, _, _, _ in anchor_matches:
                    phone_path, old_phone = self.find_nearby_value_path(
                        original_entries,
                        anchor_path,
                        validator=self.is_phone_text,
                        max_scan=25,
                    )

                    if phone_path and self.set_target_at_original_path(
                        target_path_map,
                        phone_path,
                        phone,
                    ):
                        changed = True
                        break

                audit.append(
                    {
                        "항목": f"18페이지 {anchor}",
                        "결과": "입력" if changed else "위치미확인",
                        "값": phone,
                        "건수": 1 if changed else 0,
                    }
                )

            # 25페이지: 원본 설비행의 값 경로를 읽어 같은 위치에 입력
            for item in self.collect_equipment_data():
                equipment_name = item.get("설비명", "").strip()

                if not equipment_name:
                    continue

                matches = self.find_original_paths(
                    original_entries,
                    [equipment_name],
                )

                if not matches:
                    audit.append(
                        {
                            "항목": f"25페이지 {equipment_name}",
                            "결과": "설비명미확인",
                            "값": "",
                            "건수": 0,
                        }
                    )
                    continue

                selected = bool(item.get("선택"))
                new_values = [
                    "○" if selected else "-",
                    str(item.get("전체수량", 0))
                    if selected
                    else "-",
                    str(item.get("점검수량", 0))
                    if selected
                    else "-",
                ]

                start_path = matches[0][0]
                start_indexes = [
                    index
                    for index, (path, _, _) in enumerate(original_entries)
                    if path == start_path
                ]
                written = 0

                if start_indexes:
                    start_index = start_indexes[0]

                    for path, _, text in original_entries[
                        start_index + 1 : start_index + 35
                    ]:
                        normalized = self.normalize_hwp_text(text)

                        if normalized in [
                            "○",
                            "-",
                            "대상",
                            "비대상",
                        ] or normalized.replace(",", "").isdigit():
                            if written < len(new_values):
                                if self.set_target_at_original_path(
                                    target_path_map,
                                    path,
                                    new_values[written],
                                ):
                                    written += 1

                        if written == len(new_values):
                            break

                audit.append(
                    {
                        "항목": f"25페이지 {equipment_name}",
                        "결과": (
                            "입력"
                            if written == 3
                            else f"부분입력({written}/3)"
                        ),
                        "값": " / ".join(new_values),
                        "건수": written,
                    }
                )

            mapped_xml = ET.tostring(
                target_root,
                encoding="unicode",
            )

            set_result = target_hwp.SetTextFile(
                mapped_xml,
                "HWPML2X",
                "",
            )

            if set_result is False:
                raise RuntimeError(
                    "원본 구조를 반영한 HWPML을 대상 문서에 적용하지 못했습니다."
                )

            lines = [
                "원본·빈양식 구조매핑 결과",
                "=" * 60,
                "",
            ]

            for item in audit:
                lines.append(
                    f"[{item.get('항목', '')}] "
                    f"{item.get('결과', '')} / "
                    f"값={item.get('값', '')} / "
                    f"건수={item.get('건수', 0)}"
                )

            Path(audit_path).write_text(
                "\n".join(lines),
                encoding="utf-8",
            )

            return audit

        finally:
            if original_hwp is not None:
                try:
                    original_hwp.Quit()
                except Exception:
                    pass

    def generate_report_files(self):
        self.save_current_inspection_detail()

        if not self.validate_report_data(show_message=False):
            self.validate_report_data(show_message=True)
            return

        preflight_issues = self.collect_report_criterion_preflight_issues()
        if preflight_issues:
            action, issue = self.show_report_preflight_dialog(
                preflight_issues
            )
            if action == "move":
                self.move_to_report_preflight_issue(issue)
                return
            if action != "continue":
                return

        output_dir = Path(
            self.report_output_dir.text().strip()
        ).expanduser()

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(
                self,
                "출력폴더 생성 실패",
                str(error),
            )
            return

        filename = self.safe_filename(
            self.report_filename.text().strip()
        )
        hwp_path = output_dir / f"{filename}_생성본.hwp"
        pdf_path = output_dir / f"{filename}_생성본.pdf"
        audit_path = output_dir / f"{filename}_1~27쪽_입력결과.txt"

        template_path = Path(
            self.report_template_path.text().strip()
        ).resolve()

        if template_path == hwp_path.resolve():
            QMessageBox.critical(
                self,
                "경로 오류",
                "자동화템플릿과 생성본 경로가 같습니다. "
                "출력폴더를 templates 폴더와 다르게 지정하십시오.",
            )
            return

        try:
            shutil.copy2(template_path, hwp_path)
        except OSError as error:
            QMessageBox.critical(
                self,
                "자동화템플릿 복사 실패",
                f"빈 양식 자동화템플릿을 복사하지 못했습니다.\n\n{error}",
            )
            return

        try:
            import win32com.client
        except ImportError:
            QMessageBox.critical(
                self,
                "한글 자동화 모듈 없음",
                "pywin32가 설치되어 있지 않습니다.",
            )
            return

        hwp = None

        try:
            hwp = win32com.client.Dispatch(
                "HWPFrame.HwpObject"
            )
            hwp.XHwpWindows.Item(0).Visible = True

            opened = hwp.Open(str(hwp_path))

            if opened is False:
                raise RuntimeError(
                    "복사된 1~27쪽 자동화템플릿을 열지 못했습니다."
                )

            inserted_fields = self.put_all_field_values(
                hwp
            )

            audit_path.write_text(
                "필드기반 보고서 입력 결과\n"
                + "=" * 50
                + "\n\n"
                + "\n".join(inserted_fields),
                encoding="utf-8",
            )

            try:
                hwp.HAction.Run("UpdateAllField")
            except Exception:
                pass

            if self.generate_hwp_checkbox.isChecked():
                hwp.SaveAs(str(hwp_path), "HWP", "")

            if self.generate_pdf_checkbox.isChecked():
                hwp.SaveAs(str(pdf_path), "PDF", "")

            inserted_count = len(inserted_fields)
            not_found_count = (
                len(self.build_field_values())
                - inserted_count
            )

            message = (
                "필드 기반으로 1~27쪽 입력을 완료했습니다.\n\n"
                f"자동입력 처리: {inserted_count}건\n"
                f"확인 필요: {not_found_count}건\n\n"
                f"HWP: {hwp_path}\n"
                f"PDF: {pdf_path if self.generate_pdf_checkbox.isChecked() else '미생성'}\n"
                f"입력결과표: {audit_path}"
            )

            self.status_label.setText(
                "생성본 작성 완료"
            )

            try:
                hwp.Clear(1)
                hwp.Open(str(hwp_path))
                hwp.XHwpWindows.Item(0).Visible = True
            except Exception:
                pass

            QMessageBox.information(
                self,
                "보고서 생성 완료",
                message
                + "\n\n현재 열린 문서는 templates의 템플릿이 아니라 "
                  "생성보고서 폴더의 '_생성본.hwp'입니다.",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "보고서 생성 실패",
                "1~27쪽 자동화템플릿 입력 중 오류가 발생했습니다.\n\n"
                f"{error}\n\n"
                f"복사된 파일:\n{hwp_path}",
            )

        finally:
            if hwp is not None:
                try:
                    hwp.Quit()
                except Exception:
                    pass

    def open_report_output_dir(self):
        folder_text = self.report_output_dir.text().strip()

        if not folder_text:
            folder_text = str(Path.cwd() / "생성보고서")
            self.report_output_dir.setText(folder_text)

        folder = Path(folder_text)

        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            QMessageBox.critical(
                self,
                "출력폴더 오류",
                str(error),
            )
            return

        try:
            import subprocess
            subprocess.Popen(
                ["explorer", str(folder.resolve())],
                shell=False,
            )
        except OSError as error:
            QMessageBox.information(
                self,
                "출력폴더",
                f"{folder.resolve()}\n\n{error}",
            )
    def collect_page13_data(self):
        """구버전 호환용. v3.14.1부터 13페이지 입력은 사용하지 않는다."""
        return []

    def collect_emergency_data(self):
        """구버전 호환용. v3.14.1부터 18페이지 비상연락망 입력은 사용하지 않는다."""
        return []


    def clear_all(self):
        answer = QMessageBox.question(
            self,
            "신규 프로젝트",
            "현재 입력내용을 지우고 신규 프로젝트를 시작하시겠습니까?",
        )

        if answer != QMessageBox.Yes:
            return

        previous_site = self.current_site_name_for_audit()
        self.write_audit(
            "신규 프로젝트",
            site=previous_site,
            detail="현재 입력내용 초기화 후 신규 프로젝트 시작",
        )

        self.site_name.clear()
        self.address.clear()
        self.building_use.setCurrentIndex(0)
        self.inspection_basis.setCurrentIndex(0)
        self.total_area.clear()
        self.households.setValue(0)
        self.update_inspection_basis_ui()
        self.ground_floors.setValue(0)
        self.basement_floors.setValue(0)

        today = QDate.currentDate()

        self.completion_date.setDate(today)
        self.reference_date.setDate(today)
        self.management_entity.clear()
        self.representative.clear()
        self.phone.clear()
        self.maintenance_manager.clear()
        self.maintenance_grade.setCurrentIndex(0)
        self.contract_start.setDate(today)
        self.contract_end.setDate(today)
        self.inspection_start.setDate(today)
        self.inspection_end.setDate(today)
        self.report_date.setDate(today)
        self.submit_authority.clear()
        self.inspection_method.setCurrentIndex(0)

        self.aging_table.setRowCount(0)

        current_year = QDate.currentDate().year()
        row_index = 0
        for year in range(current_year - 2, current_year + 1):
            for energy_type, unit in [("가스", "N㎥"), ("전기", "kWh")]:
                self.energy_table.item(row_index, 0).setText(str(year))
                self.energy_table.item(row_index, 1).setText(energy_type)
                self.energy_table.item(row_index, 2).setText(unit)
                for col in range(3, self.energy_table.columnCount()):
                    self.energy_table.item(row_index, col).setText("")
                row_index += 1
        self.energy_result_summary.clear()
        self.energy_operation_opinion.setPlainText(
            "최근 3개년 에너지 사용량 추이를 참고하여 계절별 부하에 맞는 "
            "설비 운전 스케줄 조정, 설정값 최적화, 노후설비 개선 및 "
            "대기전력 차단 등을 통한 에너지 절감을 권장함."
        )
        self.aging_overall_opinion.clear()
        self.lifespan_source_combo.setCurrentText(
            "한국부동산원 유형고정자산 내용연수표"
        )
        self.system_operation_table.setRowCount(0)
        self.design_measure_table.setRowCount(0)
        self.defect_improvement_table.setRowCount(0)
        self.five_year_plan_table.setRowCount(0)

        if hasattr(self, "survey_file_path"):
            self.last_survey_file = ""
            self.survey_file_path.clear()
            self.survey_result_label.setText(
                "불러온 조사표 없음"
            )

        if hasattr(self, "shot_checklist_preview"):
            self.shot_checklist_preview.clear()

        for row in range(self.report_checklist_table.rowCount()):
            combo = self.report_checklist_table.cellWidget(row, 2)
            combo.setCurrentIndex(0)
            self.report_checklist_table.item(row, 3).setText("")
        self.update_checklist_summary()

        self.equipment_table.blockSignals(True)

        try:
            for row in range(self.equipment_table.rowCount()):
                self.equipment_table.item(row, 0).setCheckState(
                    Qt.Unchecked
                )
                self.equipment_table.item(row, 3).setText("0")
                self.equipment_table.item(row, 4).setText("0")
                self.equipment_table.item(row, 6).setText("0")
        finally:
            self.equipment_table.blockSignals(False)

        self.technician_table.setRowCount(0)
        self.equipment_register_table.setRowCount(0)
        self.target_table.setRowCount(0)
        self.inspection_detail_table.setRowCount(0)
        self.detail_equipment_combo.clear()
        self.inspection_results = {}
        self.cause_analysis = []
        self.previous_project_data = {}
        self.previous_project_path = ""
        self.previous_compare_results = []
        self.performance_calculations = []

        if hasattr(self, "performance_calc_saved_table"):
            self.performance_calc_saved_table.setRowCount(0)
            self.clear_performance_calc_inputs()

        if hasattr(self, "cause_analysis_table"):
            self.cause_analysis_table.setRowCount(0)
        if hasattr(self, "previous_compare_table"):
            self.previous_compare_table.setRowCount(0)
            self.previous_compare_summary.clear()
            self.previous_project_label.setText(
                "전년도 프로젝트 미선택"
            )

        self.current_detail_equipment_key = None
        self.target_selections = []
        self.photo_records = []
        self.current_photo_id = None
        self.update_equipment_summary()
        self.update_register_summary()

        self.current_file = None
        self.menu.setCurrentRow(0)
        self.status_label.setText("신규 프로젝트를 시작합니다.")

    @staticmethod
    def set_date_value(widget, date_text):
        date_value = QDate.fromString(date_text, "yyyy-MM-dd")

        if date_value.isValid():
            widget.setDate(date_value)
        else:
            widget.setDate(QDate.currentDate())

    @staticmethod
    def safe_filename(filename):
        invalid_characters = '<>:"/\\|?*'

        for character in invalid_characters:
            filename = filename.replace(character, "_")

        return filename.strip()


def main():
    while True:
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        auth = AuthManager()

        if not auth.has_users():
            setup = FirstAdminDialog(auth)
            if setup.exec() != QDialog.Accepted:
                return

        login = LoginDialog(auth)
        if login.exec() != QDialog.Accepted:
            return

        window = PerformanceInspectionApp(
            current_user=login.user,
            auth_manager=auth,
        )
        window.show()

        result = app.exec()

        # 1001 = 로그아웃 후 로그인 화면으로 복귀
        if result == 1001:
            continue

        return



if __name__ == "__main__":
    main()
