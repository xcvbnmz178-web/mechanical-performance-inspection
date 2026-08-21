import json
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox

from .compatibility import normalize_legacy_judgments


PROJECT_VERSION = "3.16.1"


def serialize_project_data(project_data, indent=None):
    return json.dumps(
        project_data,
        ensure_ascii=False,
        indent=indent,
    )


def deserialize_project_data(text):
    return json.loads(text)


def write_project_file(file_path, project_data):
    Path(file_path).write_text(
        serialize_project_data(project_data, indent=4),
        encoding="utf-8",
    )


def read_project_file(file_path):
    return deserialize_project_data(
        Path(file_path).read_text(encoding="utf-8")
    )


class ProjectServiceMixin:
    def save_project(self):
        final_validation = self.validate_final_judgments(
            show_message=True
        )
        if not final_validation["통과"]:
            return

        self.save_current_inspection_detail()
        site_data = self.collect_site_data()

        if not self.validate_site_data(site_data):
            self.menu.setCurrentRow(0)
            return

        try:
            project_data = {
                "프로그램버전": PROJECT_VERSION,
                "최종수정자": {
                    "아이디": self.current_user.get("id", ""),
                    "사용자명": self.current_user.get(
                        "display_name", ""
                    ),
                    "수정일시": datetime.now().astimezone().isoformat(
                        timespec="seconds"
                    ),
                },
                "현장정보": site_data,
                "설비현황": self.collect_equipment_data(),
                "참여기술자": self.collect_technician_data(),
                "장비대장": self.collect_equipment_register_data(),
                "점검대상선정": self.collect_target_selection_data(),
                "설비별점검결과": self.inspection_results,
                "원인분석": self.collect_cause_analysis_data(),
                "전년도비교": {
                    "전년도프로젝트경로": getattr(
                        self, "previous_project_path", ""
                    ),
                    "비교결과": getattr(
                        self, "previous_compare_results", []
                    ),
                },
                "성능계산": getattr(
                    self, "performance_calculations", []
                ),
                "사진관리": self.collect_photo_data(),
                "시스템검토": self.collect_system_review_data(),
                "노후도분석": self.collect_aging_data(),
                "성능개선계획": self.collect_improvement_data(),
                "에너지분석": self.collect_energy_data(),
                "보고서자체검증": self.collect_checklist_data(),
                "대상조사표파일": getattr(
                    self,
                    "last_survey_file",
                    "",
                ),
                "최근사진폴더": self.last_photo_source_dir,
                "최근현장사진폴더": getattr(
                    self,
                    "last_field_photo_directory",
                    "",
                ),
            }

            # 저장 창을 띄우기 전에 직렬화 가능 여부를 먼저 검증
            serialize_project_data(project_data)

        except Exception as error:
            QMessageBox.critical(
                self,
                "프로젝트 자료 수집 실패",
                "프로젝트 데이터를 만드는 중 오류가 발생했습니다.\n\n"
                f"{type(error).__name__}: {error}",
            )
            return

        default_name = self.safe_filename(
            site_data.get("현장명", "") or "성능점검현장"
        )

        # 최근 프로젝트 저장 폴더 기억
        saved_dir = self.settings.value(
            "last_project_directory",
            str(Path.cwd()),
            type=str,
        )
        if not saved_dir or not Path(saved_dir).exists():
            saved_dir = str(Path.cwd())

        default_path = (
            Path(saved_dir)
            / f"{default_name}_성능점검프로젝트.json"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "프로젝트 저장",
            str(default_path),
            "성능점검 프로젝트 (*.json)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        try:
            write_project_file(file_path, project_data)

            self.current_file = file_path

            project_dir = str(
                Path(file_path).resolve().parent
            )
            self.settings.setValue(
                "last_project_directory",
                project_dir,
            )
            self.settings.sync()

            self.status_label.setText(
                f"프로젝트 저장 완료: {file_path}"
            )

            self.write_audit(
                "프로젝트 저장",
                target=Path(file_path).name,
                detail=str(file_path),
            )

            QMessageBox.information(
                self,
                "저장 완료",
                "프로젝트를 정상적으로 저장했습니다.\n\n"
                f"{file_path}",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "저장 실패",
                "프로젝트 파일을 저장하지 못했습니다.\n\n"
                f"{type(error).__name__}: {error}",
            )


    def open_project(self):
        saved_dir = self.settings.value(
            "last_project_directory",
            str(Path.cwd()),
            type=str,
        )
        if not saved_dir or not Path(saved_dir).exists():
            saved_dir = str(Path.cwd())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "프로젝트 열기",
            saved_dir,
            "성능점검 프로젝트 (*.json)",
        )

        if not file_path:
            return

        try:
            project_data = read_project_file(file_path)

            self.load_site_data(project_data.get("현장정보", {}))
            self.load_equipment_data(
                project_data.get("설비현황", [])
            )
            self.load_technician_data(
                project_data.get("참여기술자", [])
            )
            self.inspection_results = project_data.get(
                "설비별점검결과", {}
            )

            # 구버전 판정값을 v3.14 최종판정 체계로 변환
            normalize_legacy_judgments(
                self.inspection_results,
                self.normalize_final_judgment,
            )
            self.cause_analysis = project_data.get(
                "원인분석", []
            )

            previous_compare = project_data.get(
                "전년도비교", {}
            )
            self.previous_project_path = previous_compare.get(
                "전년도프로젝트경로", ""
            )
            self.previous_compare_results = previous_compare.get(
                "비교결과", []
            )
            self.performance_calculations = project_data.get(
                "성능계산", []
            )

            self.load_equipment_register_data(
                project_data.get("장비대장", [])
            )
            self.load_target_selection_data(
                project_data.get("점검대상선정", [])
            )
            self.load_photo_data(
                project_data.get("사진관리", [])
            )
            self.load_system_review_data(
                project_data.get("시스템검토", {})
            )
            self.load_aging_data(
                project_data.get("노후도분석", [])
            )
            self.load_improvement_data(
                project_data.get("성능개선계획", [])
            )
            self.load_energy_data(
                project_data.get("에너지분석", {})
            )
            self.load_checklist_data(
                project_data.get("보고서자체검증", [])
            )
            self.migrate_special_cause_analysis()
            self.load_cause_analysis_data(
                self.cause_analysis
            )
            survey_file = project_data.get(
                "대상조사표파일",
                "",
            )
            self.last_survey_file = survey_file

            if survey_file and Path(survey_file).parent.exists():
                self.last_survey_directory = str(
                    Path(survey_file).parent
                )
                self.settings.setValue(
                    "last_survey_directory",
                    self.last_survey_directory,
                )

            if hasattr(self, "survey_file_path"):
                self.survey_file_path.setText(
                    survey_file
                )
                self.survey_result_label.setText(
                    (
                        f"연결된 조사표: "
                        f"{Path(survey_file).name}"
                    )
                    if survey_file
                    else "불러온 조사표 없음"
                )
            saved_photo_dir = project_data.get(
                "최근사진폴더", str(Path.home())
            )
            self.last_photo_source_dir = (
                saved_photo_dir
                if Path(saved_photo_dir).exists()
                else str(Path.home())
            )

            saved_field_photo_dir = project_data.get(
                "최근현장사진폴더",
                self.settings.value(
                    "last_field_photo_directory",
                    str(Path.home()),
                    type=str,
                ),
            )
            self.last_field_photo_directory = (
                saved_field_photo_dir
                if saved_field_photo_dir
                else str(Path.home())
            )

            self.refresh_saved_performance_calculations()

            if hasattr(self, "previous_project_label"):
                if self.previous_project_path:
                    self.previous_project_label.setText(
                        "전년도 연결 프로젝트: "
                        + Path(self.previous_project_path).name
                    )
                else:
                    self.previous_project_label.setText(
                        "전년도 프로젝트 미선택"
                    )

            self.current_file = file_path

            self.write_audit(
                "프로젝트 열기",
                target=Path(file_path).name,
                detail=str(file_path),
            )

            project_dir = str(
                Path(file_path).resolve().parent
            )
            self.settings.setValue(
                "last_project_directory",
                project_dir,
            )
            self.settings.sync()

            self.menu.setCurrentRow(0)
            self.status_label.setText(
                f"프로젝트 불러오기 완료: {file_path}"
            )

            QMessageBox.information(
                self,
                "불러오기 완료",
                "프로젝트를 정상적으로 불러왔습니다.",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "불러오기 실패",
                f"프로젝트를 불러오지 못했습니다.\n\n{error}",
            )
