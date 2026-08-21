from pathlib import Path
from tempfile import gettempdir

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .service import (
    DEFAULT_ELECTRIC_TOE_FACTOR,
    DEFAULT_GAS_TOE_FACTOR,
    build_energy_review_data,
    calculate_change_rate,
    calculate_composition_ratio,
    calculate_primary_intensity,
    calculate_toe,
    format_energy_review_summary,
    normalize_energy_type,
)


def _comparison_for_table(yearly_values, year):
    points = sorted(
        (str(item_year), value)
        for item_year, value in (yearly_values or {}).items()
    )
    for index, (item_year, current) in enumerate(points):
        if item_year != str(year) or index == 0:
            continue
        previous = points[index - 1][1]
        return (current - previous) / previous * 100.0 if previous > 0 else None
    return None


class EnergyManagerMixin:
    def create_energy_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("8. 에너지 사용량 검토")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        factor_layout = QHBoxLayout()
        factor_layout.addWidget(QLabel("가스 TOE 환산계수"))
        self.gas_toe_factor = QLineEdit(str(DEFAULT_GAS_TOE_FACTOR))
        factor_layout.addWidget(self.gas_toe_factor)
        factor_layout.addWidget(QLabel("전기 TOE 환산계수"))
        self.electric_toe_factor = QLineEdit(str(DEFAULT_ELECTRIC_TOE_FACTOR))
        factor_layout.addWidget(self.electric_toe_factor)
        factor_layout.addStretch()
        layout.addLayout(factor_layout)

        self.energy_table = QTableWidget(6, 7)
        self.energy_table.setHorizontalHeaderLabels(
            ["연도", "종류", "단위", "총 사용량", "TOE/년", "TOE 비율[%]", "사용량 전년대비"]
        )
        self.energy_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        current_year = QDate.currentDate().year()
        row = 0
        for year in range(current_year - 2, current_year + 1):
            for energy_type, unit in [
                ("도시가스사용량", "N㎥"),
                ("전력사용량", "kWh"),
            ]:
                self.energy_table.setItem(row, 0, QTableWidgetItem(str(year)))
                self.energy_table.setItem(row, 1, QTableWidgetItem(energy_type))
                self.energy_table.setItem(row, 2, QTableWidgetItem(unit))
                self.energy_table.setItem(row, 3, QTableWidgetItem(""))
                self.energy_table.setItem(row, 4, QTableWidgetItem(""))
                self.energy_table.setItem(row, 5, QTableWidgetItem(""))
                self.energy_table.setItem(row, 6, QTableWidgetItem(""))
                for col in [4, 5, 6]:
                    self.energy_table.item(row, col).setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                row += 1
        self.energy_table.itemChanged.connect(self.calculate_energy_analysis)
        self.energy_table.setMinimumHeight(230)
        self.energy_table.setMaximumHeight(330)
        layout.addWidget(self.energy_table)

        energy_buttons = QHBoxLayout()
        calc_button = QPushButton("TOE·비율·증감률 계산")
        calc_button.clicked.connect(self.calculate_energy_analysis)
        chart_button = QPushButton("에너지 그래프 다시 생성")
        chart_button.clicked.connect(self.create_energy_chart)
        energy_buttons.addWidget(calc_button)
        energy_buttons.addWidget(chart_button)
        add_source_button = QPushButton("에너지원 행 추가")
        add_source_button.clicked.connect(self.add_energy_source_row)
        remove_source_button = QPushButton("선택 행 삭제")
        remove_source_button.clicked.connect(self.remove_selected_energy_rows)
        energy_buttons.addWidget(add_source_button)
        energy_buttons.addWidget(remove_source_button)
        energy_buttons.addStretch()
        layout.addLayout(energy_buttons)

        self.primary_energy_table = QTableWidget(3, 8)
        self.primary_energy_table.setHorizontalHeaderLabels(
            [
                "연도", "연면적/세대", "도시가스 TOE", "전력 TOE",
                "총 TOE", "총 TOE 증감량", "총 TOE 증감률[%]", "기술검토 상태",
            ]
        )
        self.primary_energy_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        for row in range(3):
            for col in range(8):
                self.primary_energy_table.setItem(row, col, QTableWidgetItem(""))
                self.primary_energy_table.item(row, col).setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable
                )
        self.primary_energy_table.setMinimumHeight(150)
        self.primary_energy_table.setMaximumHeight(230)
        layout.addWidget(self.primary_energy_table)

        self.energy_chart_label = QLabel("에너지 그래프 미생성")
        self.energy_chart_label.setMinimumHeight(180)
        self.energy_chart_label.setMaximumHeight(240)
        self.energy_chart_label.setAlignment(Qt.AlignCenter)
        self.energy_chart_label.setScaledContents(True)
        self.energy_chart_label.setStyleSheet(
            "border: 1px solid #cbd5e1; background: white;"
        )
        self.energy_result_summary = QPlainTextEdit()
        self.energy_result_summary.setObjectName("legacy_energy_result_summary")
        self.energy_result_summary.hide()

        self.energy_operation_opinion = QPlainTextEdit()
        self.energy_operation_opinion.setPlainText(
            "최근 3개년 에너지 사용량 추이를 참고하여 계절별 부하에 맞는 "
            "설비 운전 스케줄 조정, 설정값 최적화, 노후설비 개선 및 "
            "대기전력 차단 등을 통한 에너지 절감을 권장함."
        )
        self.energy_operation_opinion.setMaximumHeight(100)
        layout.addWidget(self.energy_operation_opinion)
        layout.addWidget(self.energy_chart_label)

        buttons = QHBoxLayout()
        prev_button = QPushButton("이전: 노후도·개선계획")
        prev_button.clicked.connect(lambda: self.menu.setCurrentRow(6))
        next_button = QPushButton("다음: 자체검증")
        next_button.clicked.connect(lambda: self.menu.setCurrentRow(8))
        buttons.addWidget(prev_button)
        buttons.addStretch()
        buttons.addWidget(next_button)
        layout.addLayout(buttons)
        return page


    def add_energy_source_row(self, year="", energy_type="기타 에너지원", unit=""):
        row = self.energy_table.rowCount()
        self.energy_table.insertRow(row)
        for column, value in enumerate((year, energy_type, unit, "", "", "", "")):
            item = QTableWidgetItem(str(value))
            if column in {4, 5, 6}:
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.energy_table.setItem(row, column, item)
        return row

    def remove_selected_energy_rows(self):
        rows = sorted(
            {index.row() for index in self.energy_table.selectedIndexes()},
            reverse=True,
        )
        for row in rows:
            self.energy_table.removeRow(row)
        if rows:
            self.calculate_energy_analysis()


    def _calculate_energy_analysis_legacy(self, _item=None):
        if not hasattr(self, "energy_table"):
            return

        self.energy_table.blockSignals(True)

        try:
            try:
                gas_factor = float(
                    self.gas_toe_factor.text().strip()
                )
            except ValueError:
                gas_factor = DEFAULT_GAS_TOE_FACTOR

            try:
                elec_factor = float(
                    self.electric_toe_factor.text().strip()
                )
            except ValueError:
                elec_factor = DEFAULT_ELECTRIC_TOE_FACTOR

            by_year = {}

            for row in range(self.energy_table.rowCount()):
                year_item = self.energy_table.item(row, 0)
                type_item = self.energy_table.item(row, 1)
                usage_item = self.energy_table.item(row, 3)

                year = year_item.text().strip() if year_item else ""
                energy_type = (
                    type_item.text().strip()
                    if type_item else ""
                )
                usage_text = (
                    usage_item.text()
                    .replace(",", "")
                    .strip()
                    if usage_item else ""
                )

                try:
                    usage = float(usage_text or 0)
                except ValueError:
                    usage = 0.0

                factor = (
                    gas_factor
                    if energy_type == "가스"
                    else elec_factor
                )
                toe = calculate_toe(usage, factor)

                toe_item = self.energy_table.item(row, 4)
                if toe_item is None:
                    toe_item = QTableWidgetItem("")
                    self.energy_table.setItem(row, 4, toe_item)
                toe_item.setText(
                    f"{toe:,.2f}" if usage else ""
                )

                by_year.setdefault(
                    year,
                    {},
                )[energy_type] = {
                    "usage": usage,
                    "toe": toe,
                    "row": row,
                }

            years = sorted(
                year for year in by_year
                if str(year).strip()
            )

            previous_toe = {
                "가스": None,
                "전기": None,
            }

            for year in years:
                total_toe = sum(
                    value["toe"]
                    for value in by_year[year].values()
                )

                for energy_type in ["가스", "전기"]:
                    data = by_year[year].get(
                        energy_type
                    )
                    if not data:
                        continue

                    ratio = calculate_composition_ratio(
                        data["toe"],
                        total_toe,
                    )

                    ratio_item = self.energy_table.item(
                        data["row"], 5
                    )
                    if ratio_item is None:
                        ratio_item = QTableWidgetItem("")
                        self.energy_table.setItem(
                            data["row"], 5, ratio_item
                        )
                    ratio_item.setText(
                        f"{ratio:.2f}"
                        if total_toe else ""
                    )

                    previous = previous_toe[
                        energy_type
                    ]
                    change_rate = calculate_change_rate(
                        data["toe"],
                        previous,
                    )
                    change = (
                        f"{change_rate:+.2f}%"
                        if change_rate is not None
                        else ""
                    )

                    change_item = self.energy_table.item(
                        data["row"], 6
                    )
                    if change_item is None:
                        change_item = QTableWidgetItem("")
                        self.energy_table.setItem(
                            data["row"], 6, change_item
                        )
                    change_item.setText(change)

                    previous_toe[energy_type] = data["toe"]

            # 1차에너지 원단위 기준 결정
            try:
                gross_area = float(
                    self.total_area.text()
                    .replace(",", "")
                    .strip()
                    or 0
                )
            except ValueError:
                gross_area = 0.0

            households = (
                self.households.value()
                if hasattr(self, "households")
                else 0
            )

            if gross_area > 0:
                denominator = gross_area
                denominator_label = f"{gross_area:,.2f}㎡"
                unit_suffix = "㎡"
            elif households > 0:
                denominator = float(households)
                denominator_label = f"{households:,}세대"
                unit_suffix = "세대"
            else:
                denominator = 0.0
                denominator_label = ""
                unit_suffix = "㎡"

            # 현재 기준에 따라 표 머리글도 자동 변경
            self.primary_energy_table.setHorizontalHeaderLabels(
                [
                    "연도",
                    "연면적/세대",
                    f"가스 1차에너지(kWh/{unit_suffix})",
                    f"전기 1차에너지(kWh/{unit_suffix})",
                    f"합계(kWh/{unit_suffix})",
                ]
            )

            for row in range(
                self.primary_energy_table.rowCount()
            ):
                for col in range(
                    self.primary_energy_table.columnCount()
                ):
                    item = self.primary_energy_table.item(
                        row, col
                    )
                    if item is None:
                        item = QTableWidgetItem("")
                        self.primary_energy_table.setItem(
                            row, col, item
                        )
                    item.setText("")

            for row, year in enumerate(
                years[:self.primary_energy_table.rowCount()]
            ):
                gas_toe = (
                    by_year[year]
                    .get("가스", {})
                    .get("toe", 0)
                )
                elec_toe = (
                    by_year[year]
                    .get("전기", {})
                    .get("toe", 0)
                )

                gas_intensity = calculate_primary_intensity(
                    gas_toe,
                    denominator,
                )
                elec_intensity = calculate_primary_intensity(
                    elec_toe,
                    denominator,
                )

                values = [
                    year,
                    denominator_label,
                    (
                        f"{gas_intensity:.2f}"
                        if denominator else ""
                    ),
                    (
                        f"{elec_intensity:.2f}"
                        if denominator else ""
                    ),
                    (
                        f"{gas_intensity + elec_intensity:.2f}"
                        if denominator else ""
                    ),
                ]

                for col, value in enumerate(values):
                    self.primary_energy_table.item(
                        row, col
                    ).setText(str(value))

            summary = self.build_energy_summary(
                by_year
            )
            auto_opinion = self.build_energy_auto_opinion(
                by_year
            )

            if auto_opinion:
                summary = (
                    summary.strip()
                    + ("\n" if summary.strip() else "")
                    + "종합판단: "
                    + auto_opinion
                )

            if not denominator:
                summary += (
                    "\n1차에너지 원단위 계산을 위해 "
                    "연면적 또는 세대수 입력이 필요함."
                )

            self.energy_result_summary.setPlainText(
                summary.strip()
            )

            # 운용개선의견도 데이터 방향에 따라 자동 갱신
            # 단, 사용자가 별도 상세의견을 작성한 경우는 보존
            old_operation = self.energy_operation_opinion.toPlainText().strip()
            default_like = (
                not old_operation
                or old_operation.startswith("최근 3개년")
                or "설비 운전 스케줄 조정" in old_operation
                or old_operation.startswith("[자동]")
            )
            if default_like:
                self.energy_operation_opinion.setPlainText(
                    "[자동] " + auto_opinion
                )

            self.refresh_energy_linked_inspection_comments()

        finally:
            self.energy_table.blockSignals(False)


    def build_energy_auto_opinion(self, by_year):
        years = sorted(
            year for year in by_year
            if str(year).strip()
        )
        if len(years) < 2:
            return "최근 2개년 이상 에너지 사용량 입력 시 자동 종합판단이 생성됩니다."

        first_year = years[0]
        last_year = years[-1]

        def usage(year, kind):
            return (
                by_year.get(year, {})
                .get(kind, {})
                .get("usage", 0)
            )

        def toe(year, kind):
            return (
                by_year.get(year, {})
                .get(kind, {})
                .get("toe", 0)
            )

        fg = usage(first_year, "가스")
        lg = usage(last_year, "가스")
        fe = usage(first_year, "전기")
        le = usage(last_year, "전기")

        first_total = toe(first_year, "가스") + toe(
            first_year, "전기"
        )
        last_total = toe(last_year, "가스") + toe(
            last_year, "전기"
        )

        dg = lg - fg if fg and lg else 0
        de = le - fe if fe and le else 0
        dt = last_total - first_total

        if first_total <= 0 or last_total <= 0:
            return (
                "에너지원별 사용량은 입력되었으나 총 TOE 비교자료가 부족하여 "
                "증감 추이의 정량판단은 보류함."
            )

        total_rate = dt / first_total * 100.0

        if total_rate >= 5.0 and de < 0 and dg > 0:
            return (
                "전기 사용량은 감소하였으나 가스 사용량 증가로 총 에너지 사용량이 "
                f"{first_year}년 대비 {last_year}년 약 {abs(total_rate):.2f}% 증가함. "
                "열원설비 운전시간, 난방부하, 설정조건 및 연소효율을 추가 검토할 필요가 있음."
            )

        if total_rate >= 5.0:
            return (
                f"총 에너지 사용량이 {first_year}년 대비 {last_year}년 "
                f"약 {abs(total_rate):.2f}% 증가함. 설비 운전시간, 부하 변동, "
                "설정값 및 주요 기기의 효율 저하 여부에 대한 원인분석이 필요함."
            )

        if total_rate <= -5.0 and dg > 0:
            return (
                f"총 에너지 사용량은 {first_year}년 대비 {last_year}년 "
                f"약 {abs(total_rate):.2f}% 감소하였으나 가스 사용량은 증가함. "
                "열원설비의 운전방식과 연소효율을 별도로 확인할 필요가 있음."
            )

        if total_rate <= -5.0:
            return (
                f"총 에너지 사용량이 {first_year}년 대비 {last_year}년 "
                f"약 {abs(total_rate):.2f}% 감소하여 전반적인 사용량 추이는 양호함. "
                "현재의 운전방식을 유지하되 지속적인 사용량 모니터링이 필요함."
            )

        return (
            f"총 에너지 사용량의 변화가 {first_year}년 대비 {last_year}년 "
            f"{total_rate:+.2f}% 수준으로 큰 변동 없이 관리되고 있음. "
            "현행 운전조건을 유지하면서 계절별 부하 및 설비효율을 지속 관리할 필요가 있음."
        )

    def current_energy_linked_comment(self):
        """
        4-3 '에너지 사용량' 점검항목의 기술적소견에 사용할 문구.
        8번 에너지 분석표의 실제 입력값을 사용한다.
        """
        if not hasattr(self, "energy_table"):
            return ""
        return format_energy_review_summary(
            self.current_energy_review_data()
        )

    def refresh_energy_linked_inspection_comments(self):
        """
        에너지표 수정 후 이미 ○ 합격으로 판정된 '에너지 사용량' 항목의
        자동 기술소견만 갱신한다. 사용자가 직접 작성한 문구는 보존한다.
        """
        comment = self.current_energy_linked_comment()
        if not comment:
            return

        self.save_current_inspection_detail()

        for key, rows in self.inspection_results.items():
            for item in rows:
                if (
                    item.get("점검내용") != "에너지 사용량"
                    or not self.is_final_pass(
                        item.get("판정")
                    )
                ):
                    continue

                old = str(
                    item.get("기술적소견", "")
                ).strip()

                auto_like = (
                    not old
                    or old.startswith("[에너지자동]")
                    or "최근 3개년 에너지 사용량" in old
                    or "총 TOE:" in old
                    or old.startswith("현장 확인, 작동시험")
                )

                if auto_like:
                    item["기술적소견"] = (
                        "[에너지자동] " + comment
                    )

    def build_energy_summary(self, by_year):
        years = sorted(by_year)
        if not years:
            return ""
        lines = []
        for energy_type in ["가스", "전기"]:
            valid = [
                (year, by_year[year].get(energy_type, {}).get("usage", 0))
                for year in years
                if by_year[year].get(energy_type, {}).get("usage", 0) > 0
            ]
            if len(valid) >= 2:
                y1, v1 = valid[0]
                y2, v2 = valid[-1]
                diff = v2 - v1
                rate = diff / v1 * 100
                unit = "N㎥" if energy_type == "가스" else "kWh"
                direction = "증가" if diff > 0 else "감소"
                lines.append(
                    f"{energy_type}: {y1}년 대비 {y2}년 "
                    f"{abs(diff):,.0f}{unit} {direction}, 약 {abs(rate):.2f}%"
                )
        total_first = sum(by_year[years[0]].get(t, {}).get("toe", 0) for t in ["가스", "전기"])
        total_last = sum(by_year[years[-1]].get(t, {}).get("toe", 0) for t in ["가스", "전기"])
        if total_first > 0:
            rate = (total_last - total_first) / total_first * 100
            lines.append(
                f"총 TOE: {years[0]}년 대비 {years[-1]}년 "
                f"{'증가' if rate > 0 else '감소'} 약 {abs(rate):.2f}%"
            )
        return "\n".join(lines)

    def _create_energy_chart_legacy(self):
        """
        외부 matplotlib 없이 PySide6 QPainter로 그래프를 생성한다.
        프로그램 설치환경과 무관하게 바로 동작한다.
        """
        self.calculate_energy_analysis()

        years = []
        gas = []
        electricity = []

        for row in range(0, self.energy_table.rowCount(), 2):
            year_item = self.energy_table.item(row, 0)
            gas_item = self.energy_table.item(row, 4)
            elec_item = self.energy_table.item(row + 1, 4)

            year = year_item.text().strip() if year_item else ""
            try:
                gas_value = float(
                    gas_item.text().replace(",", "").strip()
                    if gas_item else 0
                )
            except ValueError:
                gas_value = 0.0

            try:
                elec_value = float(
                    elec_item.text().replace(",", "").strip()
                    if elec_item else 0
                )
            except ValueError:
                elec_value = 0.0

            if year:
                years.append(year)
                gas.append(gas_value)
                electricity.append(elec_value)

        if not years or max(gas + electricity + [0]) <= 0:
            QMessageBox.information(
                self,
                "그래프 생성",
                "그래프를 만들 에너지 사용량이 없습니다.",
            )
            return

        width = 900
        height = 330
        left = 80
        right = 35
        top = 55
        bottom = 60

        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("white"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 제목
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        painter.drawText(
            0, 8, width, 30,
            Qt.AlignHCenter | Qt.AlignVCenter,
            "에너지원별 TOE 사용량 추이",
        )

        graph_w = width - left - right
        graph_h = height - top - bottom
        max_value = max(gas + electricity)
        max_value *= 1.15

        # 격자와 Y축
        painter.setFont(QFont("Malgun Gothic", 8))
        for step in range(6):
            ratio = step / 5
            y = top + graph_h - ratio * graph_h
            value = max_value * ratio

            painter.setPen(QPen(QColor("#d1d5db"), 1))
            painter.drawLine(left, int(y), left + graph_w, int(y))

            painter.setPen(QColor("#4b5563"))
            painter.drawText(
                5,
                int(y) - 8,
                left - 12,
                16,
                Qt.AlignRight | Qt.AlignVCenter,
                f"{value:.1f}",
            )

        painter.setPen(QPen(QColor("#374151"), 2))
        painter.drawLine(left, top, left, top + graph_h)
        painter.drawLine(left, top + graph_h, left + graph_w, top + graph_h)

        if len(years) == 1:
            x_positions = [left + graph_w / 2]
        else:
            x_positions = [
                left + i * graph_w / (len(years) - 1)
                for i in range(len(years))
            ]

        # X축 연도
        painter.setFont(QFont("Malgun Gothic", 9))
        painter.setPen(QColor("#374151"))
        for x, year in zip(x_positions, years):
            painter.drawText(
                int(x) - 40,
                top + graph_h + 8,
                80,
                24,
                Qt.AlignHCenter | Qt.AlignTop,
                str(year),
            )

        def draw_series(values, color, label):
            pen = QPen(QColor(color), 3)
            painter.setPen(pen)

            points = []
            for x, value in zip(x_positions, values):
                y = top + graph_h - (
                    value / max_value * graph_h
                    if max_value else 0
                )
                points.append((x, y))

            for i in range(1, len(points)):
                painter.drawLine(
                    int(points[i - 1][0]),
                    int(points[i - 1][1]),
                    int(points[i][0]),
                    int(points[i][1]),
                )

            painter.setBrush(QColor(color))
            for x, y in points:
                painter.drawEllipse(
                    int(x) - 5,
                    int(y) - 5,
                    10,
                    10,
                )

            painter.setBrush(Qt.NoBrush)

        draw_series(gas, "#d97706", "가스")
        draw_series(electricity, "#2563eb", "전기")

        # 범례
        legend_y = height - 24
        painter.setFont(QFont("Malgun Gothic", 9))

        painter.setPen(QPen(QColor("#d97706"), 3))
        painter.drawLine(width // 2 - 90, legend_y, width // 2 - 60, legend_y)
        painter.setPen(QColor("#111827"))
        painter.drawText(width // 2 - 55, legend_y - 10, 50, 20, Qt.AlignLeft, "가스")

        painter.setPen(QPen(QColor("#2563eb"), 3))
        painter.drawLine(width // 2 + 10, legend_y, width // 2 + 40, legend_y)
        painter.setPen(QColor("#111827"))
        painter.drawText(width // 2 + 45, legend_y - 10, 50, 20, Qt.AlignLeft, "전기")

        painter.end()

        chart_dir = (
            Path(self.current_file).resolve().parent
            if self.current_file
            else Path.cwd()
        )
        chart_path = chart_dir / "_energy_primary_chart.png"
        pixmap.save(str(chart_path), "PNG")

        self.energy_chart_label.setPixmap(
            pixmap.scaled(
                self.energy_chart_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )
        self.energy_chart_path = str(chart_path)
        self.status_label.setText(
            "에너지 TOE 그래프를 생성했습니다."
        )


    def calculate_energy_analysis(self, _item=None, refresh_chart=True):
        """Calculate table outputs from the general energy-source model."""
        if not hasattr(self, "energy_table"):
            return
        self.energy_table.blockSignals(True)
        try:
            review = self.current_energy_review_data()
            series_by_type = review["series_by_type"]
            total_toe = review["total_toe"]
            for row in range(self.energy_table.rowCount()):
                year = self.table_item_text(self.energy_table, row, 0)
                raw_type = self.table_item_text(self.energy_table, row, 1)
                unit = self.table_item_text(self.energy_table, row, 2)
                key, _definition = normalize_energy_type(raw_type)
                series = series_by_type.get(key)
                if series and unit and series.get("unit") != unit:
                    series = series_by_type.get(f"{key}@{unit}")
                toe = (series or {}).get("yearly_toe", {}).get(year)
                ratio = (
                    toe / total_toe[year] * 100.0
                    if toe is not None and total_toe.get(year, 0) > 0 else None
                )
                comparison = _comparison_for_table(
                    (series or {}).get("yearly_values", {}), year
                )
                outputs = (
                    f"{toe:,.3f}" if toe is not None else "",
                    f"{ratio:.2f}" if ratio is not None else "",
                    (
                        f"{comparison:+.2f}%"
                        if comparison is not None else ""
                    ),
                )
                for column, value in zip((4, 5, 6), outputs):
                    item = self.energy_table.item(row, column)
                    if item is None:
                        item = QTableWidgetItem("")
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        self.energy_table.setItem(row, column, item)
                    item.setText(value)

            years = review["years"]
            self.primary_energy_table.setRowCount(max(3, len(years)))
            self.primary_energy_table.setColumnCount(8)
            self.primary_energy_table.setHorizontalHeaderLabels(
                [
                    "연도", "연면적/세대", "도시가스 TOE", "전력 TOE",
                    "총 TOE", "총 TOE 증감량", "총 TOE 증감률[%]", "기술검토 상태",
                ]
            )
            for row in range(self.primary_energy_table.rowCount()):
                for column in range(8):
                    item = self.primary_energy_table.item(row, column)
                    if item is None:
                        item = QTableWidgetItem("")
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                        self.primary_energy_table.setItem(row, column, item)
                    item.setText("")
            gas = series_by_type.get("city_gas", {}).get("yearly_toe", {})
            electric = series_by_type.get("electricity", {}).get("yearly_toe", {})
            total_points = sorted(total_toe.items())
            total_comparisons = {}
            for index, (year, current_total) in enumerate(total_points):
                change = rate = None
                if index > 0:
                    previous_total = total_points[index - 1][1]
                    change = current_total - previous_total
                    if previous_total > 0:
                        rate = change / previous_total * 100.0
                total_comparisons[year] = (change, rate)
            for row, year in enumerate(years):
                change, rate = total_comparisons.get(year, (None, None))
                status = (
                    "비교불가" if rate is None
                    else "증가원인확인" if rate >= review["increase_review_pct"]
                    else "데이터 정상"
                )
                for column, value in enumerate(
                    (
                        year, "", gas.get(year), electric.get(year),
                        total_toe.get(year), change, rate, status,
                    )
                ):
                    self.primary_energy_table.item(row, column).setText(
                        "" if value is None else (
                            f"{value:+.2f}" if column == 6 and isinstance(value, float)
                            else f"{value:+.3f}" if column == 5 and isinstance(value, float)
                            else f"{value:.3f}" if isinstance(value, float)
                            else str(value)
                        )
                    )
            current_opinion = self.energy_operation_opinion.toPlainText().strip()
            if not current_opinion or current_opinion.startswith("[자동]"):
                self.energy_operation_opinion.setPlainText(
                    "[자동] " + review["review_note"] + "\n"
                    f"기술검토 상태: {review['technical_status_label']}"
                )
            self.refresh_energy_linked_inspection_comments()
            if hasattr(self, "refresh_energy_review_proposals"):
                self.refresh_energy_review_proposals()
        finally:
            self.energy_table.blockSignals(False)
        if refresh_chart:
            self._render_energy_chart(review, show_messages=False)

    def current_energy_review_data(self):
        """Return shared energy data for charts and system review."""
        try:
            gas_factor = float(self.gas_toe_factor.text().strip())
        except (TypeError, ValueError):
            gas_factor = DEFAULT_GAS_TOE_FACTOR
        try:
            electric_factor = float(self.electric_toe_factor.text().strip())
        except (TypeError, ValueError):
            electric_factor = DEFAULT_ELECTRIC_TOE_FACTOR
        return build_energy_review_data(
            self.collect_table_text(self.energy_table),
            gas_factor,
            electric_factor,
        )

    @staticmethod
    def _draw_energy_chart_panel(painter, rect, years, series, title, unit):
        x0, y0, width, height = rect
        left, right, top, bottom = 78, 24, 34, 38
        graph_w = width - left - right
        graph_h = height - top - bottom
        values = [
            value for _label, items, _color in series for value in items
            if isinstance(value, (int, float))
        ]
        max_value = max(values + [0.0]) * 1.15 or 1.0
        painter.setPen(QColor("#111827"))
        painter.setFont(QFont("Malgun Gothic", 10, QFont.Bold))
        painter.drawText(x0, y0, width, 26, Qt.AlignHCenter, f"{title} [{unit}]")
        gx, gy = x0 + left, y0 + top
        painter.setFont(QFont("Malgun Gothic", 8))
        value_format = ",.3f" if str(unit).upper() == "TOE" else ",.1f"
        axis_format = ",.3f" if str(unit).upper() == "TOE" else ",.2f"
        for step in range(5):
            ratio = step / 4
            y = gy + graph_h - ratio * graph_h
            painter.setPen(QPen(QColor("#e5e7eb"), 1))
            painter.drawLine(gx, int(y), gx + graph_w, int(y))
            painter.setPen(QColor("#4b5563"))
            painter.drawText(
                x0, int(y) - 8, left - 8, 16,
                Qt.AlignRight, format(max_value * ratio, axis_format),
            )
        painter.setPen(QPen(QColor("#374151"), 1))
        painter.drawLine(gx, gy, gx, gy + graph_h)
        painter.drawLine(gx, gy + graph_h, gx + graph_w, gy + graph_h)
        group_width = graph_w / max(len(years), 1)
        x_positions = [
            gx + group_width * (index + 0.5)
            for index in range(len(years))
        ]
        for x, year in zip(x_positions, years):
            painter.drawText(
                int(x) - 36, gy + graph_h + 5, 72, 22,
                Qt.AlignHCenter, str(year),
            )
        legend_x = gx
        series_count = max(len(series), 1)
        bar_width = max(8.0, min(54.0, group_width * 0.72 / series_count))
        for series_index, (label, items, color) in enumerate(series):
            painter.setPen(QPen(QColor(color), 1))
            painter.setBrush(QColor(color))
            for x, value in zip(x_positions, items):
                if value is None:
                    continue
                bar_height = value / max_value * graph_h
                bar_x = x - (bar_width * series_count) / 2 + bar_width * series_index
                bar_y = gy + graph_h - bar_height
                painter.drawRect(
                    int(bar_x), int(bar_y), max(1, int(bar_width - 2)), int(bar_height)
                )
                painter.setPen(QColor("#374151"))
                painter.drawText(
                    int(bar_x) - 18, max(gy, int(bar_y) - 18),
                    int(bar_width) + 36, 16, Qt.AlignHCenter,
                    format(value, value_format),
                )
                painter.setPen(QPen(QColor(color), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(legend_x, y0 + 14, 20, 12)
            painter.setPen(QColor("#111827"))
            painter.drawText(legend_x + 30, y0 + 10, 100, 20, Qt.AlignLeft, label)
            legend_x += 130

    def _create_energy_chart_electric_gas(self):
        """Create separate usage-unit panels and a common TOE panel."""
        try:
            self.calculate_energy_analysis()
            review = self.current_energy_review_data()
            years = review["years"]
            series = review["series"]
            if not years or not any(series["total_toe"]):
                reason = "연도별 전기·가스 사용량 자료가 없어 그래프를 생성할 수 없습니다."
                self.energy_chart_label.clear()
                self.energy_chart_label.setText(reason)
                QMessageBox.information(self, "그래프 생성 불가", reason)
                return False

            width, panel_height = 1000, 230
            pixmap = QPixmap(width, panel_height * 3)
            pixmap.fill(QColor("white"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            self._draw_energy_chart_panel(
                painter, (0, 0, width, panel_height), years,
                (("전기", series["electricity_usage"], "#2563eb"),),
                "연도별 전기사용량 추세", "kWh",
            )
            self._draw_energy_chart_panel(
                painter, (0, panel_height, width, panel_height), years,
                (("가스", series["gas_usage"], "#d97706"),),
                "연도별 가스사용량 추세", "N㎥",
            )
            self._draw_energy_chart_panel(
                painter, (0, panel_height * 2, width, panel_height), years,
                (
                    ("가스 TOE", series["gas_toe"], "#d97706"),
                    ("전기 TOE", series["electricity_toe"], "#2563eb"),
                    ("총 TOE", series["total_toe"], "#059669"),
                ),
                "에너지원별 TOE 및 총 TOE 추세", "TOE",
            )
            painter.end()
            chart_dir = (
                Path(self.current_file).resolve().parent
                if self.current_file
                else Path(gettempdir()) / "performance_inspection"
            )
            chart_dir.mkdir(parents=True, exist_ok=True)
            chart_path = chart_dir / "_energy_trend_chart.png"
            if not pixmap.save(str(chart_path), "PNG"):
                raise RuntimeError("그래프 PNG 저장에 실패했습니다.")
            self.energy_chart_label.setPixmap(
                pixmap.scaled(
                    self.energy_chart_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
            self.energy_chart_path = str(chart_path)
            self.status_label.setText(
                f"에너지 사용량 그래프를 생성했습니다: {chart_path}"
            )
            return True
        except Exception as error:
            reason = (
                f"에너지 그래프를 생성하지 못했습니다: "
                f"{type(error).__name__}: {error}"
            )
            self.energy_chart_label.clear()
            self.energy_chart_label.setText(reason)
            QMessageBox.warning(self, "그래프 생성 실패", reason)
            return False

    def _show_energy_chart_pixmap(self, pixmap, chart_path):
        """Validate the saved PNG and update the actual on-screen QLabel."""
        if not chart_path.is_file() or chart_path.stat().st_size <= 0:
            raise RuntimeError("그래프 PNG 파일이 생성되지 않았거나 비어 있습니다.")
        loaded = QPixmap()
        if not loaded.load(str(chart_path)) or loaded.isNull():
            raise RuntimeError("생성된 그래프 PNG를 QPixmap으로 불러오지 못했습니다.")
        self._energy_chart_pixmap = loaded
        self.energy_chart_label.clear()
        self.energy_chart_label.setPixmap(loaded)
        self.energy_chart_label.setVisible(True)
        if self.energy_chart_label.pixmap() is None or self.energy_chart_label.pixmap().isNull():
            raise RuntimeError("그래프 QLabel에 QPixmap을 설정하지 못했습니다.")
        self.energy_chart_path = str(chart_path)
        self.energy_chart_error_detail = ""

    def _render_energy_chart(self, review, show_messages=False):
        """Render shared review data and update both PNG and the live UI widget."""
        try:
            years = review["years"]
            sources = review["energy_series"]
            if not years or not sources:
                reason = "관리주체 제공 에너지원별 사용량 자료가 없어 그래프를 생성할 수 없습니다."
                self.energy_chart_label.clear()
                self.energy_chart_label.setText(reason)
                self.energy_chart_error_detail = reason
                if show_messages:
                    QMessageBox.information(self, "그래프 생성 불가", reason)
                return False

            raw_panels = []
            for source in sources:
                values = [source["yearly_values"].get(year) for year in years]
                if any(value is not None for value in values):
                    raw_panels.append(
                        (
                            f"연도별 {source['display_name']}",
                            source["unit"] or "원자료 단위",
                            ((source["display_name"], values, source["color"]),),
                        )
                    )
            toe_series = []
            if review.get("total_toe"):
                toe_series.append(
                    (
                        "총 TOE",
                        [review["total_toe"].get(year) for year in years],
                        "#059669",
                    )
                )
            toe_panel = (
                ("연도별 총 TOE", "TOE", tuple(toe_series))
                if toe_series else None
            )
            if not raw_panels and toe_panel is None:
                reason = "유효한 연도별 사용량이 없어 그래프를 생성할 수 없습니다."
                self.energy_chart_label.clear()
                self.energy_chart_label.setText(reason)
                self.energy_chart_error_detail = reason
                if show_messages:
                    QMessageBox.information(self, "그래프 생성 불가", reason)
                return False

            width, panel_height = 1200, 170
            raw_rows = max(1, (len(raw_panels) + 1) // 2)
            total_rows = raw_rows + (1 if toe_panel else 0)
            pixmap = QPixmap(width, panel_height * total_rows)
            pixmap.fill(QColor("white"))
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            half_width = width // 2
            for index, (title, unit, series) in enumerate(raw_panels):
                row, column = divmod(index, 2)
                self._draw_energy_chart_panel(
                    painter,
                    (column * half_width, row * panel_height, half_width, panel_height),
                    years,
                    series,
                    title,
                    unit,
                )
            if toe_panel:
                title, unit, series = toe_panel
                self._draw_energy_chart_panel(
                    painter,
                    (0, raw_rows * panel_height, width, panel_height),
                    years,
                    series,
                    title,
                    unit,
                )
            painter.end()
            chart_dir = (
                Path(self.current_file).resolve().parent
                if self.current_file
                else Path(gettempdir()) / "performance_inspection"
            )
            chart_dir.mkdir(parents=True, exist_ok=True)
            chart_path = chart_dir / "_energy_trend_chart.png"
            if not pixmap.save(str(chart_path), "PNG"):
                raise RuntimeError("그래프 PNG 저장에 실패했습니다.")
            self._show_energy_chart_pixmap(pixmap, chart_path)
            self.status_label.setText(
                f"에너지원별 사용량 그래프를 생성했습니다: {chart_path}"
            )
            return True
        except Exception as error:
            reason = (
                f"에너지 그래프를 생성하지 못했습니다: "
                f"{type(error).__name__}: {error}"
            )
            self.energy_chart_label.clear()
            self.energy_chart_label.setText(reason)
            self.energy_chart_error_detail = reason
            self.status_label.setText(reason)
            if show_messages:
                QMessageBox.warning(self, "그래프 생성 실패", reason)
            return False

    def create_energy_chart(self):
        """Explicitly recalculate and regenerate the live chart."""
        self.calculate_energy_analysis(refresh_chart=False)
        return self._render_energy_chart(
            self.current_energy_review_data(), show_messages=True
        )

    def collect_energy_data(self):
        rows = self.collect_table_text(self.energy_table)
        return {
            "에너지사용량": rows,
            "1차에너지분석": self.collect_table_text(self.primary_energy_table),
            "결과요약": self.energy_result_summary.toPlainText().strip(),
            "운용개선의견": self.energy_operation_opinion.toPlainText().strip(),
            "가스TOE계수": self.gas_toe_factor.text().strip(),
            "전기TOE계수": self.electric_toe_factor.text().strip(),
            "그래프경로": getattr(self, "energy_chart_path", ""),
        }


    def update_energy_change_rates(self, _item=None):
        if not hasattr(self, "energy_table"):
            return

        self.energy_table.blockSignals(True)

        try:
            totals = []

            for row in range(self.energy_table.rowCount()):
                total = 0.0

                for col in [1, 2, 3, 4]:
                    item = self.energy_table.item(row, col)

                    if item is None:
                        item = QTableWidgetItem("")
                        self.energy_table.setItem(row, col, item)

                    text = item.text().replace(",", "").strip()

                    try:
                        total += float(text or 0)
                    except ValueError:
                        pass

                totals.append(total)

            for row in range(self.energy_table.rowCount()):
                result = ""

                if row > 0 and totals[row - 1] > 0:
                    rate = calculate_change_rate(
                        totals[row],
                        totals[row - 1],
                    )
                    result = f"{rate:+.1f}%"

                rate_item = self.energy_table.item(row, 6)

                if rate_item is None:
                    rate_item = QTableWidgetItem("")
                    rate_item.setFlags(
                        Qt.ItemIsEnabled | Qt.ItemIsSelectable
                    )
                    self.energy_table.setItem(row, 6, rate_item)

                rate_item.setText(result)

        finally:
            self.energy_table.blockSignals(False)

    def load_energy_data(self, data):
        rows = data.get("에너지사용량", data.get("연도별사용량", []))
        mapping = ["연도", "종류", "단위", "총 사용량", "TOE/년", "비율[%]", "전년대비"]
        self.energy_table.blockSignals(True)
        try:
            self.energy_table.setRowCount(max(6, len(rows)))
            for row in range(self.energy_table.rowCount()):
                saved = rows[row] if row < len(rows) else {}
                for col, key in enumerate(mapping):
                    item = self.energy_table.item(row, col)
                    if item is None:
                        item = QTableWidgetItem("")
                        self.energy_table.setItem(row, col, item)
                    item.setText(str(saved.get(key, "")))
                    if col in {4, 5, 6}:
                        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        finally:
            self.energy_table.blockSignals(False)
        self.gas_toe_factor.setText(
            str(data.get("가스TOE계수", DEFAULT_GAS_TOE_FACTOR))
        )
        self.electric_toe_factor.setText(
            str(data.get("전기TOE계수", DEFAULT_ELECTRIC_TOE_FACTOR))
        )
        self.energy_result_summary.setPlainText(data.get("결과요약", ""))
        self.energy_operation_opinion.setPlainText(
            data.get("운용개선의견", "")
        )
        self.calculate_energy_analysis()
