import math
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox


class SurveyManagerMixin:
    def apply_standard_survey(self, text):
        tokens = self.standard_survey_tokens(text)
        filled = []

        site_name = self.standard_value_after_token(
            tokens,
            ["건물명"],
        )
        address = self.standard_value_after_token(
            tokens,
            ["주소"],
        )
        completion_text = self.standard_value_after_token(
            tokens,
            ["준공일자"],
        )
        area_text = self.standard_value_after_token(
            tokens,
            ["연면적/세대수"],
        )
        manager_name = self.standard_value_after_token(
            tokens,
            ["유지관리담당자"],
        )
        manager_phone = self.standard_value_after_token(
            tokens,
            ["연락처"],
        )

        if site_name:
            self.site_name.setText(site_name)
            filled.append("건물명")

        if address:
            self.address.setText(address)
            filled.append("주소")

        completion_date = self.survey_parse_date(
            completion_text
        )
        if completion_date:
            self.set_date_value(
                self.completion_date,
                completion_date,
            )
            filled.append("준공일자")

        area = self.survey_first_number(area_text)
        if area:
            self.inspection_basis.setCurrentIndex(0)
            self.total_area.setText(area)
            filled.append("연면적")

        if manager_name:
            self.maintenance_manager.setText(
                manager_name
            )
            filled.append("유지관리담당자")

        if manager_phone:
            self.phone.setText(manager_phone)
            filled.append("연락처")

        equipment_results = (
            self.parse_standard_survey_equipment(tokens)
        )

        self.equipment_table.blockSignals(True)
        try:
            for result in equipment_results:
                row = self.find_equipment_row(
                    result["설비명"]
                )
                if row < 0:
                    continue

                self.equipment_table.item(
                    row, 0
                ).setCheckState(Qt.Checked)
                self.equipment_table.item(
                    row, 3
                ).setText(
                    str(result["전체수량"])
                )
                self.equipment_table.item(
                    row, 4
                ).setText(
                    str(result["전체수량"])
                )
                self.equipment_table.item(
                    row, 6
                ).setText(
                    str(result["점검수량"])
                )
        finally:
            self.equipment_table.blockSignals(False)

        self.update_equipment_summary()

        valid_equipment = [
            item
            for item in equipment_results
            if item["전체수량"] > 0
        ]
        zero_equipment = [
            item["설비명"]
            for item in equipment_results
            if item["전체수량"] <= 0
        ]

        return {
            "표준서식인식": bool(
                site_name
                and (
                    "기계설비 성능점검 수량 산출"
                    in str(text)
                    or "기계설비 성능검사 대상"
                    in str(text)
                )
            ),
            "현장정보": filled,
            "설비결과": valid_equipment,
            "수량미확인": zero_equipment,
        }

    def parse_survey_text(self, text):
        lines = self.survey_normalize_lines(text)
        filled = []
        equipment_count = 0

        site_name = self.survey_value_after_label(
            lines,
            ["건물명", "건축물명", "현장명", "명칭(상호)", "상호(명칭)"],
        )
        address = self.survey_value_after_label(
            lines,
            ["현장주소", "주소", "소재지"],
        )
        area_text = self.survey_value_after_label(
            lines,
            ["연면적"],
        )
        household_text = self.survey_value_after_label(
            lines,
            ["세대수"],
        )
        usage = self.survey_value_after_label(
            lines,
            ["주용도", "건축물 용도", "용도"],
        )
        completion_text = self.survey_value_after_label(
            lines,
            ["준공일자", "준공일", "사용승인일", "사용승인일자"],
        )
        floor_text = self.survey_value_after_label(
            lines,
            ["건물구조", "층수"],
        )
        management_name = self.survey_value_after_label(
            lines,
            ["관리주체 성명", "관리주체명", "관리주체"],
        )
        management_address = self.survey_value_after_label(
            lines,
            ["관리주체 주소"],
        )
        management_phone = self.survey_value_after_label(
            lines,
            ["관리주체 전화번호", "전화번호", "전화/팩스"],
        )
        base_date_text = self.survey_value_after_label(
            lines,
            ["성능점검 기준일", "점검기준일"],
        )
        manager1_text = self.survey_value_after_label(
            lines,
            ["책임 기계설비유지관리자", "책임유지관리자", "선임인"],
        )
        manager2_text = self.survey_value_after_label(
            lines,
            ["보조 기계설비유지관리자", "보조유지관리자"],
        )

        if site_name:
            self.site_name.setText(site_name)
            filled.append("현장명")

        if address:
            self.address.setText(address)
            filled.append("주소")

        if usage:
            self.building_use.setCurrentText(usage)
            filled.append("용도")

        area = self.survey_first_number(area_text)
        households = self.survey_first_number(household_text)

        if households and int(float(households)) > 0:
            self.inspection_basis.setCurrentIndex(1)
            self.households.setValue(int(float(households)))
            filled.append("세대수")
        elif area and float(area) > 0:
            self.inspection_basis.setCurrentIndex(0)
            self.total_area.setText(area)
            filled.append("연면적")

        completion_date = self.survey_parse_date(completion_text)
        if completion_date:
            self.set_date_value(self.completion_date, completion_date)
            filled.append("준공일")

        base_date = self.survey_parse_date(base_date_text)
        if base_date:
            self.set_date_value(self.reference_date, base_date)
            filled.append("성능점검 기준일")

        ground, basement = self.survey_parse_floors(
            floor_text or "\n".join(lines)
        )
        if ground:
            self.ground_floors.setValue(ground)
            filled.append("지상층수")
        if basement:
            self.basement_floors.setValue(basement)
            filled.append("지하층수")

        if management_name:
            self.management_entity.setText(management_name)
            filled.append("관리주체")

        if management_address:
            self.management_address.setText(management_address)
            filled.append("관리주체 주소")

        if management_phone:
            self.phone.setText(management_phone)
            filled.append("관리주체 전화번호")

        if manager1_text:
            manager1_name = re.sub(
                r"(특급|고급|중급|초급|보조|\(|\)|책임|선임인)",
                " ",
                manager1_text,
            ).strip()
            self.maintenance_manager.setText(manager1_name)
            grade = self.survey_extract_grade(manager1_text)
            if grade:
                self.maintenance_grade.setCurrentText(grade)
            filled.append("책임 유지관리자")

        if manager2_text:
            manager2_name = re.sub(
                r"(특급|고급|중급|초급|보조|\(|\)|책임|선임인)",
                " ",
                manager2_text,
            ).strip()
            self.maintenance_manager2.setText(manager2_name)
            grade = self.survey_extract_grade(manager2_text)
            if grade:
                self.maintenance_grade2.setCurrentText(grade)
            filled.append("보조 유지관리자")

        self.equipment_table.blockSignals(True)
        recognized_names = []
        missing_quantity_names = []

        try:
            matches = self.survey_find_equipment_matches(lines)

            for match in matches:
                equipment_name = match["설비명"]
                row = self.find_equipment_row(equipment_name)

                if row < 0:
                    continue

                equipment = self._equipment_list[row]
                candidates = match.get("수량후보", [])

                # 연도·점검률 등 잘못 잡힐 가능성이 큰 숫자는 제외
                filtered = []
                for value in candidates:
                    try:
                        number = int(str(value).replace(",", ""))
                    except (TypeError, ValueError):
                        continue

                    if number <= 0:
                        continue
                    if 1900 <= number <= 2100:
                        continue
                    if number > 100000:
                        continue

                    filtered.append(number)

                total = 0
                inspection_count = 0

                if equipment.get("unit") == "식":
                    # 1식 설비는 설비명이 확인되면 수량 없이도 선택
                    total = 1
                    inspection_count = 1
                elif filtered:
                    total = filtered[0]
                    inspection_count = math.ceil(
                        total * equipment["rate"] / 100
                    )
                    inspection_count = max(
                        1,
                        inspection_count,
                    )

                    if len(filtered) >= 2:
                        possible = filtered[1]
                        if 0 < possible <= total:
                            inspection_count = possible
                else:
                    # 설비명은 확인됐으나 수량을 읽지 못한 경우
                    # 종류는 선택하고 수량은 사용자가 확인하도록 0 유지
                    missing_quantity_names.append(equipment_name)

                selected_item = self.equipment_table.item(row, 0)
                selected_item.setCheckState(Qt.Checked)

                self.equipment_table.item(
                    row, 3
                ).setText(str(total))
                self.equipment_table.item(
                    row, 4
                ).setText(str(total))
                self.equipment_table.item(
                    row, 6
                ).setText(str(inspection_count))

                recognized_names.append(equipment_name)

            equipment_count = len(recognized_names)

        finally:
            self.equipment_table.blockSignals(False)

        self.update_equipment_summary()
        unique_equipment = list(dict.fromkeys(recognized_names))
        unique_missing = list(dict.fromkeys(missing_quantity_names))

        self.survey_result_label.setText(
            "자동 반영: "
            + (
                ", ".join(dict.fromkeys(filled))
                if filled
                else "현장정보 없음"
            )
            + f" | 설비 {len(unique_equipment)}종 선택"
            + (
                f" | 수량확인 필요 {len(unique_missing)}종"
                if unique_missing
                else ""
            )
        )

        if unique_equipment:
            detail = (
                "인식 설비:\n- "
                + "\n- ".join(unique_equipment)
            )

            if unique_missing:
                detail += (
                    "\n\n설비명은 인식했으나 수량을 찾지 못한 항목:\n- "
                    + "\n- ".join(unique_missing)
                    + "\n\n해당 항목은 종류만 선택했으므로 전체수량을 확인해 입력하십시오."
                )

            QMessageBox.information(
                self,
                "대상조사표 인식 결과",
                detail,
            )
        else:
            QMessageBox.warning(
                self,
                "대상조사표 인식 결과",
                "현장정보는 일부 읽었지만 기계설비 종류를 찾지 못했습니다.\n\n"
                "조사표의 설비명 표기가 프로그램 목록과 다른지 확인이 필요합니다.",
            )

        self.status_label.setText(
            "대상조사표 자동입력을 완료했습니다. "
            "선택된 설비와 수량을 원자료와 대조하십시오."
        )

    def load_survey_file_path(self, file_path):
        if not file_path.exists():
            raise FileNotFoundError(
                f"파일을 찾을 수 없습니다: {file_path}"
            )

        text = self.read_survey_file_text(file_path)

        if not str(text).strip():
            raise RuntimeError(
                "파일에서 읽을 수 있는 내용이 없습니다."
            )

        self.last_survey_file = str(file_path)
        self.survey_file_path.setText(str(file_path))

        standard_result = self.apply_standard_survey(
            text
        )

        if standard_result["표준서식인식"]:
            equipment_results = standard_result[
                "설비결과"
            ]
            missing = standard_result[
                "수량미확인"
            ]

            self.survey_result_label.setText(
                f"불러오기 완료: {file_path.name} | "
                f"표준서식 인식 | "
                f"설비 {len(equipment_results)}종 선택"
                + (
                    f" | 수량 미확인 {len(missing)}종"
                    if missing
                    else ""
                )
            )

            detail_lines = [
                (
                    f"{item['설비명']}: "
                    f"전체 {item['전체수량']}, "
                    f"점검 {item['점검수량']}"
                )
                for item in equipment_results
            ]

            if missing:
                detail_lines.append("")
                detail_lines.append(
                    "수량 미확인: "
                    + ", ".join(missing)
                )

            QMessageBox.information(
                self,
                "표준 대상조사표 인식 결과",
                "\n".join(detail_lines),
            )
        else:
            # 다른 형식의 조사표는 기존 일반 인식기로 처리
            self.parse_survey_text(text)
            self.survey_result_label.setText(
                f"불러오기 완료: {file_path.name} | "
                + self.survey_result_label.text()
            )

        self.status_label.setText(
            f"대상조사표 파일을 불러왔습니다: {file_path.name}"
        )

        self.write_audit(
            "대상조사표 불러오기",
            target=file_path.name,
            detail=str(file_path),
        )

    def reload_survey_file(self):
        file_name = getattr(
            self,
            "last_survey_file",
            "",
        )

        if not file_name:
            QMessageBox.information(
                self,
                "대상조사표",
                "먼저 대상조사표 파일을 선택하십시오.",
            )
            return

        try:
            self.load_survey_file_path(
                Path(file_name)
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "대상조사표 다시 읽기 실패",
                str(error),
            )

    def clear_survey_file(self):
        self.last_survey_file = ""
        self.survey_file_path.clear()
        self.survey_result_label.setText(
            "불러온 조사표 없음"
        )
        self.status_label.setText(
            "대상조사표 파일 연결을 해제했습니다."
        )

    def import_survey_file(self):
        initial_dir = getattr(
            self,
            "last_survey_directory",
            str(Path.home()),
        )

        last_file = getattr(
            self,
            "last_survey_file",
            "",
        )
        if last_file and Path(last_file).parent.exists():
            initial_dir = str(
                Path(last_file).parent
            )

        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "대상조사표 원본 파일 불러오기",
            initial_dir,
            (
                "지원 파일 (*.hwp *.hwpx *.xlsx *.xlsm *.csv *.txt);;"
                "한글 파일 (*.hwp *.hwpx);;"
                "엑셀 파일 (*.xlsx *.xlsm);;"
                "CSV 파일 (*.csv);;"
                "텍스트 파일 (*.txt)"
            ),
        )

        if not file_name:
            return

        file_path = Path(file_name)

        # 다음 파일 선택 때 방금 사용한 폴더에서 시작
        self.last_survey_directory = str(
            file_path.parent
        )
        self.settings.setValue(
            "last_survey_directory",
            self.last_survey_directory,
        )
        self.settings.sync()

        try:
            self.load_survey_file_path(
                file_path
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "대상조사표 불러오기 실패",
                f"{file_path.name}\\n\\n{error}",
            )
