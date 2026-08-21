import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QTableWidgetItem


class ComparisonManagerMixin:

    def load_previous_project(self):
        remembered = self.settings.value(
            "last_previous_project_directory",
            self.settings.value(
                "last_project_directory",
                str(Path.cwd()),
                type=str,
            ),
            type=str,
        )
        if not remembered or not Path(remembered).exists():
            remembered = str(Path.cwd())

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "전년도 성능점검 프로젝트 선택",
            remembered,
            "성능점검 프로젝트 (*.json)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                raise ValueError("올바른 프로젝트 파일이 아닙니다.")

            self.previous_project_data = data
            self.previous_project_path = file_path

            folder = str(Path(file_path).resolve().parent)
            self.settings.setValue(
                "last_previous_project_directory",
                folder,
            )
            self.settings.sync()

            site = data.get("현장정보", {})
            site_name = site.get("현장명", "") or "현장명 미입력"
            version = data.get("프로그램버전", "구버전")

            self.previous_project_label.setText(
                f"전년도 자료: {site_name} | 버전 {version} | "
                f"{Path(file_path).name}"
            )

            self.refresh_previous_comparison()

        except Exception as error:
            QMessageBox.critical(
                self,
                "전년도 프로젝트 불러오기 실패",
                f"{type(error).__name__}: {error}",
            )

    def refresh_previous_comparison(self):
        if not self.previous_project_data:
            QMessageBox.information(
                self,
                "전년도 비교",
                "먼저 전년도 프로젝트 파일을 불러오십시오.",
            )
            return
        rows, issue_count = self.build_previous_comparison_rows()
        self.previous_compare_results = rows
        self.previous_compare_table.setRowCount(len(rows))

        for row, data in enumerate(rows):
            values = [
                data["구분"],
                data["대상"],
                data["항목"],
                data["전년"],
                data["금년"],
                data["변화"],
                data["판정"],
                data["의견"],
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if col != 7:
                    item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                self.previous_compare_table.setItem(
                    row, col, item
                )

        self.previous_compare_table.resizeRowsToContents()

        if not rows:
            summary = (
                "전년도와 비교할 수 있는 동일 장비·동일 점검항목 또는 "
                "에너지 자료가 확인되지 않았습니다."
            )
        elif issue_count:
            summary = (
                f"전년도 비교 결과 원인 확인이 필요한 변화가 "
                f"{issue_count}건 확인되었습니다. "
                f"원인분석 탭에서 금년도 조치필요 항목과 함께 검토하십시오."
            )
        else:
            summary = (
                "전년도 비교 결과 주요 성능지표 및 에너지 사용량에서 "
                "현저한 악화 징후가 확인되지 않았습니다."
            )

        self.previous_compare_summary.setPlainText(summary)
        self.status_label.setText(summary)
