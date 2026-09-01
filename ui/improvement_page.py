from PySide6.QtCore import QDate
from catalogs.lifespan import DEFAULT_LIFESPAN_SOURCE
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ImprovementPageMixin:
    def create_improvement_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("7. 내구연수에 따른 노후도 및 개선계획")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        layout.addWidget(title)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        aging_tab = QWidget()
        aging_layout = QVBoxLayout(aging_tab)
        aging_buttons = QHBoxLayout()
        refresh_button = QPushButton("장비대장에서 노후도 자동계산")
        refresh_button.setToolTip(
            "명시적 재계산 시 국토교통부 2022 매뉴얼 예시 프리셋을 적용합니다. "
            "다른 참고자료를 선택해도 해당 자료의 기준표로 자동계산하지 않습니다."
        )
        refresh_button.clicked.connect(lambda: self.refresh_aging_table(recalculate=True))

        aging_buttons.addWidget(QLabel("내용연수 적용근거"))
        self.lifespan_source_combo = QComboBox()
        self.lifespan_source_combo.addItems(self._lifespan_source_options)
        self.lifespan_source_combo.setCurrentText(
            DEFAULT_LIFESPAN_SOURCE
        )
        aging_buttons.addWidget(self.lifespan_source_combo)
        aging_buttons.addWidget(refresh_button)
        aging_buttons.addStretch()
        aging_layout.addLayout(aging_buttons)

        source_notice = QLabel(
            "내용연수는 참고기준입니다. 초과만으로 부적합 또는 교체 확정하지 않고 "
            "성능측정값·고장빈도·부품수급성·보수비용을 종합하여 판단합니다."
        )
        source_notice.setWordWrap(True)
        source_notice.setStyleSheet(
            "padding: 7px; background: #fff7d6; border: 1px solid #e6c65c;"
        )
        aging_layout.addWidget(source_notice)

        self.aging_table = QTableWidget(0, 9)
        self.aging_table.setHorizontalHeaderLabels(
            ["구분", "대상설비", "장비번호/계통명", "설치연도",
             "참고 내용연수", "사용연수", "노후도", "적용근거", "비고"]
        )
        self.aging_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        aging_layout.addWidget(self.aging_table)
        self.aging_overall_opinion = QPlainTextEdit()
        self.aging_overall_opinion.setPlaceholderText("노후도 종합 점검결과")
        self.aging_overall_opinion.setMaximumHeight(100)
        aging_layout.addWidget(self.aging_overall_opinion)
        tabs.addTab(aging_tab, "2.1 노후도")

        defect_tab = QWidget()
        defect_layout = QVBoxLayout(defect_tab)
        defect_refresh = QPushButton("성능점검표에서 부적합·개선사항 불러오기")
        defect_refresh.clicked.connect(self.refresh_defect_improvement_table)
        defect_layout.addWidget(defect_refresh)
        self.defect_improvement_table = QTableWidget(0, 4)
        self.defect_improvement_table.setHorizontalHeaderLabels(
            ["구분", "대상설비", "부적합사항", "개선사항"]
        )
        self.defect_improvement_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        defect_layout.addWidget(self.defect_improvement_table)
        tabs.addTab(defect_tab, "2.2 부적합 및 개선사항")

        plan_tab = QWidget()
        plan_layout = QVBoxLayout(plan_tab)
        plan_buttons = QHBoxLayout()
        plan_auto = QPushButton("기본 5개년 계획")
        plan_auto.clicked.connect(self.refresh_five_year_plan)

        integrated_plan = QPushButton(
            "점검·원인·노후도·에너지 통합 개선계획"
        )
        integrated_plan.clicked.connect(
            self.refresh_integrated_improvement_plan
        )

        plan_buttons.addWidget(plan_auto)
        plan_buttons.addWidget(integrated_plan)
        plan_buttons.addStretch()
        plan_layout.addLayout(plan_buttons)
        self.five_year_plan_table = QTableWidget(0, 8)
        self.five_year_plan_table.setHorizontalHeaderLabels(
            ["구분", "대상설비", "성능개선 필요성",
             "1년차", "2년차", "3년차", "4년차", "5년차"]
        )
        self.five_year_plan_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        plan_layout.addWidget(self.five_year_plan_table)
        tabs.addTab(plan_tab, "2.3 5개년 개선계획")

        buttons = QHBoxLayout()
        prev_button = QPushButton("이전: 시스템 검토")
        prev_button.clicked.connect(lambda: self.menu.setCurrentRow(5))
        next_button = QPushButton("다음: 에너지 분석")
        next_button.clicked.connect(lambda: self.menu.setCurrentRow(7))
        buttons.addWidget(prev_button)
        buttons.addStretch()
        buttons.addWidget(next_button)
        layout.addLayout(buttons)
        return page

    def refresh_five_year_plan(self):
        names = self.selected_equipment_names()
        self.five_year_plan_table.setRowCount(0)
        for name in names:
            need, years = self._improvement_defaults.get(
                name, ("정기점검 및 예방정비 실시", ["점검", "유지관리", "유지관리", "유지관리", "유지관리"])
            )
            row = self.five_year_plan_table.rowCount()
            self.five_year_plan_table.insertRow(row)
            values = [self.equipment_category(name), name, need] + years
            for col, value in enumerate(values):
                self.five_year_plan_table.setItem(
                    row, col, QTableWidgetItem(str(value))
                )

    def refresh_integrated_improvement_plan(self):
        """
        Claude v47의 장점인 '점검결과 + 노후도 + 에너지 추이' 통합 초안을
        Python 데이터 구조에 맞게 확장한다.
        내용연수 초과는 교체 확정이 아니라 상태진단/성능확인 대상으로 표현한다.
        """
        self.save_current_inspection_detail()
        self.refresh_aging_table()
        self.calculate_energy_analysis()

        analysis_rows = self.collect_cause_analysis_data()
        analysis_map = {
            (
                item.get("장비키", ""),
                str(item.get("점검번호", "")),
            ): item
            for item in analysis_rows
        }

        selected = self.selected_equipment_names()
        current_year = QDate.currentDate().year()

        plans = {
            name: {
                "need": [],
                "years": ["-", "-", "-", "-", "-"],
            }
            for name in selected
        }

        def append_need(name, text):
            if name not in plans:
                plans[name] = {
                    "need": [],
                    "years": ["-", "-", "-", "-", "-"],
                }
            if text and text not in plans[name]["need"]:
                plans[name]["need"].append(text)

        def put_action(name, year_index, action):
            if name not in plans:
                plans[name] = {
                    "need": [],
                    "years": ["-", "-", "-", "-", "-"],
                }
            if not 0 <= year_index <= 4:
                year_index = 4

            existing = plans[name]["years"][year_index]
            if existing in {"", "-"}:
                plans[name]["years"][year_index] = action
            elif action not in existing:
                plans[name]["years"][year_index] = (
                    existing + " / " + action
                )

        # 1) 조치필요 및 원인분석
        for target_row in range(self.target_table.rowCount()):
            target = self.target_row_data(target_row)
            name = target.get("설비종류", "")
            if name not in plans:
                continue

            key = self.target_key_from_row(target_row)

            for result in self.inspection_results.get(key, []):
                if not self.is_final_fail(result.get("판정")):
                    continue

                item_no = str(result.get("번호", ""))
                item_name = result.get("점검내용", "")
                analysis = analysis_map.get(
                    (key, item_no),
                    {},
                )

                special_rule, is_special = self.cause_rule_for_inspection(
                    name,
                    result,
                )

                improvement = (
                    analysis.get("개선방안", "").strip()
                    or result.get("개선방안", "").strip()
                    or (
                        special_rule.get("개선", "")
                        if is_special
                        else ""
                    )
                    or "원인 확인 후 보수·조정 및 재측정"
                )
                final_cause = analysis.get(
                    "최종원인", ""
                ).strip()
                priority = analysis.get(
                    "우선순위",
                    (
                        special_rule.get("우선순위", "B-단기")
                        if is_special
                        else "B-단기"
                    ),
                )

                need_text = (
                    f"{item_name}: "
                    + (
                        f"{final_cause} 확인"
                        if final_cause
                        else "조치필요 항목 원인 확인"
                    )
                )
                append_need(name, need_text)

                year_index = {
                    "A-즉시": 0,
                    "B-단기": 0,
                    "C-중기": 1,
                    "D-관찰관리": 2,
                }.get(priority, 0)

                put_action(
                    name,
                    year_index,
                    improvement,
                )

        # 2) 노후도
        for row in range(self.aging_table.rowCount()):
            name = self.table_item_text(
                self.aging_table, row, 1
            )
            if name not in plans:
                continue

            elapsed = self.table_item_text(
                self.aging_table, row, 5
            )
            status = self.table_item_text(
                self.aging_table, row, 6
            )

            if "교체검토" in status:
                append_need(
                    name,
                    f"참고 내용연수 초과 또는 임박(사용 {elapsed}년). "
                    "성능측정·고장빈도·부품수급성 종합검토 필요",
                )
                put_action(
                    name,
                    0,
                    "정밀상태 진단 및 성능측정",
                )
                put_action(
                    name,
                    1,
                    "진단결과에 따라 보수·교체 예산 검토",
                )

            elif status == "주의":
                append_need(
                    name,
                    f"내용연수 대비 노후화 진행(사용 {elapsed}년)",
                )
                put_action(
                    name,
                    1,
                    "주요부품 상태점검 및 예방정비",
                )
                put_action(
                    name,
                    2,
                    "성능추이 재평가",
                )

        # 3) 에너지 추이
        energy_by_year = {}
        for row in range(self.energy_table.rowCount()):
            year = self.table_item_text(
                self.energy_table, row, 0
            )
            kind = self.table_item_text(
                self.energy_table, row, 1
            )
            try:
                usage = float(
                    self.table_item_text(
                        self.energy_table, row, 3
                    ).replace(",", "")
                    or 0
                )
            except ValueError:
                usage = 0.0

            if year and kind and usage > 0:
                energy_by_year.setdefault(
                    year, {}
                )[kind] = usage

        years = sorted(energy_by_year)
        if len(years) >= 2:
            first_year = years[0]
            last_year = years[-1]

            for kind in ["가스", "전기"]:
                first = energy_by_year[
                    first_year
                ].get(kind, 0)
                last = energy_by_year[
                    last_year
                ].get(kind, 0)

                if first > 0 and last > 0:
                    change = (last - first) / first * 100.0

                    if change >= 5:
                        if kind == "가스":
                            energy_name = "열원설비(가스)"
                            energy_need = (
                                f"가스 사용량 {first_year}년 대비 "
                                f"{last_year}년 {change:.1f}% 증가"
                            )
                            action = (
                                "연소공기비·열원 운전시간·열교환 성능 분석 및 "
                                "효율개선 검토"
                            )
                        else:
                            energy_name = "동력설비(전기)"
                            energy_need = (
                                f"전기 사용량 {first_year}년 대비 "
                                f"{last_year}년 {change:.1f}% 증가"
                            )
                            action = (
                                "펌프·송풍기 대수제어, 인버터 및 운전스케줄 "
                                "최적화 검토"
                            )

                        append_need(
                            energy_name,
                            energy_need,
                        )
                        put_action(
                            energy_name,
                            0,
                            action,
                        )

        # 아무 근거가 없는 선택 설비는 기본 예방정비 문구
        for name in selected:
            if not plans[name]["need"]:
                default_need, default_years = (
                    self._improvement_defaults.get(
                        name,
                        (
                            "정기점검 및 예방정비 실시",
                            [
                                "점검",
                                "유지관리",
                                "유지관리",
                                "유지관리",
                                "유지관리",
                            ],
                        ),
                    )
                )
                append_need(name, default_need)

                for index, value in enumerate(
                    default_years[:5]
                ):
                    if value and value != "-":
                        put_action(
                            name,
                            index,
                            value,
                        )

        # 표시
        self.five_year_plan_table.setRowCount(0)

        for name, plan in plans.items():
            row = self.five_year_plan_table.rowCount()
            self.five_year_plan_table.insertRow(row)

            need_text = " / ".join(
                plan["need"][:4]
            )

            values = [
                self.equipment_category(name),
                name,
                need_text,
                *plan["years"],
            ]

            for col, value in enumerate(values):
                self.five_year_plan_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(value)),
                )

        self.five_year_plan_table.resizeRowsToContents()

        self.status_label.setText(
            "점검결과·원인분석·노후도·에너지 사용량을 종합하여 "
            f"개선계획 {self.five_year_plan_table.rowCount()}건을 작성했습니다."
        )
    def calculate_elapsed_years(self, install_year):
        try:
            year = int(str(install_year).strip())
        except (TypeError, ValueError):
            return 0

        current_year = QDate.currentDate().year()
        return max(0, current_year - year)

    def aging_status(self, elapsed, lifespan):
        if lifespan <= 0 or elapsed <= 0:
            return "참고기준 없음"

        ratio = elapsed / lifespan

        if ratio >= 1:
            return "교체검토"
        if ratio >= 0.8:
            return "주의"
        return "정상"

    def refresh_aging_table(self, *, recalculate=False):
        # 시스템검토/개선계획 갱신은 저장된 노후도 판단을 재계산하지 않는다.
        if not recalculate:
            return
        previous = {
            (row.get("대상설비", ""), row.get("장비번호계통명", "")): row
            for row in self.collect_aging_data()["노후도표"]
        }
        rows = self.collect_equipment_register_data()
        self.aging_table.setRowCount(0)
        warning_count = 0
        source = DEFAULT_LIFESPAN_SOURCE
        self.lifespan_source_combo.setCurrentText(source)
        unresolved_count = 0

        for equipment in rows:
            name = equipment.get("설비종류", "")
            install_year = equipment.get("설치연도", "")
            elapsed = self.calculate_elapsed_years(install_year)
            lifespan = self._lifespan_by_equipment.get(name)
            saved = previous.get((name, equipment.get("관리번호", "") or "전체"), {})
            unresolved = not lifespan or lifespan <= 0
            if unresolved:
                unresolved_count += 1
            status = self.aging_status(elapsed, lifespan) if not unresolved else "기준 확인 필요"

            if status == "교체검토":
                status = "교체검토(성능확인 필요)"

            if status in {"주의", "교체검토(성능확인 필요)"}:
                warning_count += 1

            row = self.aging_table.rowCount()
            self.aging_table.insertRow(row)

            values = [
                self.equipment_category(name),
                name,
                equipment.get("관리번호", "") or "전체",
                install_year,
                lifespan if not unresolved else saved.get("참고내용연수", ""),
                elapsed if elapsed else "-",
                status,
                source,
                equipment.get("비고", ""),
            ]
            if unresolved:
                values[7] = saved.get("적용근거", "")
                values[8] = " / ".join(filter(None, [saved.get("비고", ""), "기준 확인 필요"]))
                if saved.get("참고내용연수"):
                    values[5] = saved.get("사용연수", "")
                    values[6] = saved.get("노후도", "")

            for col, value in enumerate(values):
                self.aging_table.setItem(
                    row, col, QTableWidgetItem(str(value))
                )

        if warning_count:
            opinion = (
                f"선택 설비 중 참고 내용연수 대비 주의 또는 교체검토 대상이 "
                f"{warning_count}종 확인됨. 내용연수 초과만으로 부적합 판정하지 않고, "
                f"성능측정값·고장빈도·효율·주요부품 수급성·보수비용을 종합하여 "
                f"단계적 보수 또는 교체계획을 수립할 필요가 있음."
            )
        else:
            opinion = (
                "현재 입력된 설치연도와 참고 내용연수를 검토한 결과, "
                "즉시 교체가 필요한 중대 노후설비는 확인되지 않음. "
                "정기점검과 예방정비를 지속하여 성능저하를 관리할 필요가 있음."
            )

        if unresolved_count:
            opinion += f" 기준 미확정 {unresolved_count}건은 기준 확인이 필요함."
        self.aging_overall_opinion.setPlainText(opinion)
        self.status_label.setText(
            f"노후도 분석표 {self.aging_table.rowCount()}건 생성 / 기준 확인 필요 {unresolved_count}건"
        )

    def auto_draft_improvement_plan(self):
        self.save_current_inspection_detail()
        self.refresh_aging_table()

        drafts = []
        current_year = QDate.currentDate().year()

        # 1. 조치필요 점검결과
        for row in range(self.target_table.rowCount()):
            target = self.target_row_data(row)
            key = self.target_key_from_row(row)
            result_rows = self.inspection_results.get(key, [])
            failures = [
                item.get("점검내용", "")
                for item in result_rows
                if self.is_final_fail(item.get("판정"))
            ]

            if not failures:
                continue

            drafts.append(
                {
                    "설비명": target.get("설비종류", ""),
                    "관리번호": target.get("관리번호", ""),
                    "문제점": (
                        "조치필요 항목: "
                        + ", ".join(failures[:4])
                        + (
                            f" 외 {len(failures) - 4}건"
                            if len(failures) > 4
                            else ""
                        )
                    ),
                    "개선방안": (
                        "점검기준과 제조사 유지관리지침에 따라 "
                        "원인 확인 후 보수·조정하고 재점검 결과를 기록"
                    ),
                    "조치구분": "즉시보수",
                    "우선순위": "높음",
                    "예정연도": str(current_year),
                    "예상비용": "",
                    "조치완료일": "",
                }
            )

        # 2. 노후도 주의·교체검토
        for aging in self.collect_aging_data():
            status = aging.get("노후도", "")

            if status not in {"주의", "교체검토"}:
                continue

            drafts.append(
                {
                    "설비명": aging.get("설비명", ""),
                    "관리번호": aging.get("관리번호", ""),
                    "문제점": (
                        f"설치 {aging.get('설치연도', '-')}년, "
                        f"경과 {aging.get('경과연수', '-')}년, "
                        f"참고 내용연수 {aging.get('참고내용연수', '-')}년 "
                        f"({status})"
                    ),
                    "개선방안": (
                        "정밀상태 확인과 주요부품 진단을 실시하고 "
                        "성능·고장빈도·에너지효율을 검토하여 보수 또는 교체계획 수립"
                    ),
                    "조치구분": (
                        "중기교체"
                        if status == "교체검토"
                        else "관찰관리"
                    ),
                    "우선순위": (
                        "높음"
                        if status == "교체검토"
                        else "보통"
                    ),
                    "예정연도": (
                        str(current_year + 1)
                        if status == "교체검토"
                        else str(current_year + 2)
                    ),
                    "예상비용": "",
                    "조치완료일": "",
                }
            )

        # 3. 에너지원별 3개년 추이
        energy_rows = self.collect_energy_data().get(
            "연도별사용량",
            [],
        )

        for source_key, label, action in [
            (
                "전기",
                "전기",
                "펌프·송풍기 대수제어, 인버터 운전, 설정값 및 운전시간 최적화 검토",
            ),
            (
                "가스",
                "가스",
                "열원설비 연소상태, 공기비, 운전스케줄 및 열손실 저감방안 검토",
            ),
        ]:
            valid = []

            for item in energy_rows:
                try:
                    value = float(
                        str(item.get(source_key, ""))
                        .replace(",", "")
                        .strip()
                    )
                except ValueError:
                    continue

                if value > 0:
                    valid.append(
                        (
                            item.get("연도", ""),
                            value,
                        )
                    )

            if len(valid) < 2:
                continue

            first_year, first_value = valid[0]
            last_year, last_value = valid[-1]
            rate = (
                (last_value - first_value)
                / first_value
                * 100
            )

            if rate < 5:
                continue

            drafts.append(
                {
                    "설비명": f"{label} 사용 관련 설비",
                    "관리번호": "",
                    "문제점": (
                        f"{first_year}년 대비 {last_year}년 "
                        f"{label} 사용량 {rate:.1f}% 증가"
                    ),
                    "개선방안": action,
                    "조치구분": "단기개선",
                    "우선순위": "보통",
                    "예정연도": str(current_year + 1),
                    "예상비용": "",
                    "조치완료일": "",
                }
            )

        if not drafts:
            QMessageBox.information(
                self,
                "개선계획 초안",
                "초안을 만들 근거가 없습니다.\n\n"
                "불합격 판정, 설치연도, 에너지 사용량 중 "
                "하나 이상을 먼저 입력하십시오.",
            )
            return

        if self.improvement_table.rowCount() > 0:
            answer = QMessageBox.question(
                self,
                "개선계획 초안 추가",
                (
                    f"기존 개선계획 {self.improvement_table.rowCount()}건이 있습니다.\n"
                    f"자동초안 {len(drafts)}건을 아래에 추가하시겠습니까?"
                ),
            )
            if answer != QMessageBox.Yes:
                return

        for draft in drafts:
            self.add_improvement_row(draft)

        self.status_label.setText(
            f"성능개선계획 자동초안 {len(drafts)}건을 추가했습니다."
        )
        QMessageBox.information(
            self,
            "개선계획 초안 생성",
            (
                f"초안 {len(drafts)}건을 생성했습니다.\n\n"
                "자동 생성내용은 참고안이므로 책임기술자가 "
                "현장 상태와 예산을 검토하여 수정해야 합니다."
            ),
        )

    def add_improvement_row(self, data=None):
        data = data or {}
        row = self.improvement_table.rowCount()
        self.improvement_table.insertRow(row)

        equipment_combo = QComboBox()
        equipment_combo.setEditable(True)
        equipment_combo.addItems(
            [item["name"] for item in self._equipment_list]
        )
        equipment_combo.setCurrentText(
            data.get("설비명", "")
        )
        self.improvement_table.setCellWidget(
            row, 0, equipment_combo
        )

        management_item = QTableWidgetItem(
            data.get("관리번호", "")
        )
        self.improvement_table.setItem(
            row, 1, management_item
        )

        self.improvement_table.setItem(
            row, 2, QTableWidgetItem(data.get("문제점", ""))
        )
        self.improvement_table.setItem(
            row, 3, QTableWidgetItem(data.get("개선방안", ""))
        )

        action_combo = QComboBox()
        action_combo.addItems(
            ["관찰관리", "즉시보수", "단기개선", "중기교체", "장기계획"]
        )
        action_combo.setCurrentText(
            data.get("조치구분", "관찰관리")
        )
        self.improvement_table.setCellWidget(
            row, 4, action_combo
        )

        priority_combo = QComboBox()
        priority_combo.addItems(["낮음", "보통", "높음", "긴급"])
        priority_combo.setCurrentText(
            data.get("우선순위", "보통")
        )
        self.improvement_table.setCellWidget(
            row, 5, priority_combo
        )

        self.improvement_table.setItem(
            row, 6, QTableWidgetItem(data.get("예정연도", ""))
        )
        self.improvement_table.setItem(
            row, 7, QTableWidgetItem(data.get("예상비용", ""))
        )
        self.improvement_table.setItem(
            row, 8, QTableWidgetItem(data.get("조치완료일", ""))
        )

    def remove_improvement_row(self):
        row = self.improvement_table.currentRow()
        if row >= 0:
            self.improvement_table.removeRow(row)

    def collect_aging_data(self):
        keys = ["구분", "대상설비", "장비번호계통명", "설치연도",
                "참고내용연수", "사용연수", "노후도", "적용근거", "비고"]
        rows = []
        for row in range(self.aging_table.rowCount()):
            values = [
                self.aging_table.item(row, col).text()
                if self.aging_table.item(row, col) else ""
                for col in range(self.aging_table.columnCount())
            ]
            rows.append(dict(zip(keys, values)))
        return {
            "노후도표": rows,
            "내용연수적용근거": self.lifespan_source_combo.currentText(),
            "종합의견": self.aging_overall_opinion.toPlainText().strip(),
            "부적합개선사항": self.collect_table_text(self.defect_improvement_table),
            "5개년개선계획": self.collect_table_text(self.five_year_plan_table),
        }

    def collect_table_text(self, table):
        headers = [
            table.horizontalHeaderItem(col).text()
            for col in range(table.columnCount())
        ]
        rows = []
        for row in range(table.rowCount()):
            values = []
            for col in range(table.columnCount()):
                item = table.item(row, col)
                values.append(item.text() if item else "")
            rows.append(dict(zip(headers, values)))
        return rows

    def collect_improvement_data(self):
        """
        v3.9 이후에는 구형 improvement_table을 사용하지 않는다.
        현재의 부적합·개선사항 및 5개년 개선계획 표를 저장한다.
        """
        return {
            "부적합개선사항": self.collect_table_text(
                self.defect_improvement_table
            ),
            "5개년개선계획": self.collect_table_text(
                self.five_year_plan_table
            ),
        }

    def load_aging_data(self, data):
        if isinstance(data, list):
            rows = data
            opinion = ""
        else:
            rows = data.get("노후도표", [])
            opinion = data.get("종합의견", "")
        self.aging_table.setRowCount(0)
        if isinstance(data, dict):
            source = data.get(
                "내용연수적용근거",
                "현장 직접입력",
            )
            if source and self.lifespan_source_combo.findText(source) < 0:
                self.lifespan_source_combo.addItem(source)
            self.lifespan_source_combo.setCurrentText(source)
        else:
            self.lifespan_source_combo.setCurrentText("현장 직접입력")
        keys = ["구분", "대상설비", "장비번호계통명", "설치연도",
                "참고내용연수", "사용연수", "노후도", "적용근거", "비고"]
        for saved in rows:
            row = self.aging_table.rowCount()
            self.aging_table.insertRow(row)
            for col, key in enumerate(keys):
                value = saved.get(key, "")
                if key == "참고내용연수" and (value is None or not str(value).strip()):
                    value = saved.get("내구연한", "")
                if key == "적용근거" and not value:
                    value = self.lifespan_source_combo.currentText()
                self.aging_table.setItem(
                    row, col, QTableWidgetItem(str(value))
                )
        self.aging_overall_opinion.setPlainText(opinion)

    def load_improvement_data(self, data):
        """
        신·구 프로젝트 모두 허용.
        구형 리스트 데이터는 보고서 보류 전 버전 자료이므로 안전하게 무시하고,
        신형 dict 데이터는 현재 두 표에 복원한다.
        """
        self.defect_improvement_table.setRowCount(0)
        self.five_year_plan_table.setRowCount(0)

        if not isinstance(data, dict):
            return

        defect_rows = data.get("부적합개선사항", [])
        defect_headers = ["구분", "대상설비", "부적합사항", "개선사항"]

        for saved in defect_rows:
            row = self.defect_improvement_table.rowCount()
            self.defect_improvement_table.insertRow(row)
            for col, key in enumerate(defect_headers):
                self.defect_improvement_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(saved.get(key, ""))),
                )

        plan_rows = data.get("5개년개선계획", [])
        plan_headers = [
            "구분",
            "대상설비",
            "성능개선 필요성",
            "1년차",
            "2년차",
            "3년차",
            "4년차",
            "5년차",
        ]

        for saved in plan_rows:
            row = self.five_year_plan_table.rowCount()
            self.five_year_plan_table.insertRow(row)
            for col, key in enumerate(plan_headers):
                self.five_year_plan_table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(saved.get(key, ""))),
                )
