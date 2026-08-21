from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QTableWidgetItem

from catalogs.equipment_subtypes import (
    chiller_subtype_info,
    normalize_chiller_subtype,
)


PERFORMANCE_REVIEW_OPTIONS = [
    "정상",
    "주의",
    "이상",
    "판단보류",
]

PERFORMANCE_CALC_DEFS = {
    "터보냉동기": {
        "fields": [
            ("설계 냉수유량", "m³/h", "dFlow"),
            ("측정 냉수유량", "m³/h", "mFlow"),
            ("설계 냉수 입구온도", "℃", "dIn"),
            ("측정 냉수 입구온도", "℃", "mIn"),
            ("설계 냉수 출구온도", "℃", "dOut"),
            ("측정 냉수 출구온도", "℃", "mOut"),
            ("설계 냉방능력", "USRT", "dCap"),
            ("설계 동력", "kW", "dPow"),
            ("측정 동력", "kW", "mPow"),
        ],
    },
    "냉각탑": {
        "fields": [
            ("설계 냉각수 입구온도", "℃", "dIn"),
            ("측정 냉각수 입구온도", "℃", "mIn"),
            ("설계 냉각수 출구온도", "℃", "dOut"),
            ("측정 냉각수 출구온도", "℃", "mOut"),
            ("설계 외기 습구온도", "℃", "dWB"),
            ("측정 외기 습구온도", "℃", "mWB"),
            ("설계 냉각수유량", "m³/h", "dFlow"),
            ("측정 냉각수유량", "m³/h", "mFlow"),
        ],
    },
    "보일러": {
        "fields": [
            ("급수온도", "℃", "fw"),
            ("운전시간", "min", "minutes"),
            ("도시가스 사용량", "N㎥/h", "gas"),
            ("증기온도(포화)", "℃", "steamT"),
            ("증기공급량(급수량)", "kg", "steamKg"),
            ("보일러 정격용량", "kg/h", "rated"),
            ("연료발열량", "kcal/N㎥", "hv"),
        ],
    },
    "열교환기": {
        "fields": [
            ("1차측 입구온도", "℃", "p1in"),
            ("1차측 출구온도", "℃", "p1out"),
            ("1차측 유량", "LPM", "p1f"),
            ("2차측 입구온도", "℃", "p2in"),
            ("2차측 출구온도", "℃", "p2out"),
            ("2차측 유량", "LPM", "p2f"),
        ],
    },
    "펌프": {
        "fields": [
            ("설계 유량", "m³/h", "dFlow"),
            ("측정 유량", "m³/h", "mFlow"),
            ("설계 양정", "m", "dHead"),
            ("측정 토출압력", "MPa", "pDis"),
            ("측정 흡입압력", "MPa", "pSuc"),
            ("설계 전류", "A", "dAmp"),
            ("측정 전류", "A", "mAmp"),
        ],
    },
    "공기조화기": {
        "fields": [
            ("설계 급기풍량", "CMH", "dSA"),
            ("측정 급기풍량", "CMH", "mSA"),
            ("설계 환기풍량", "CMH", "dRA"),
            ("측정 환기풍량", "CMH", "mRA"),
            ("설계 정압", "mmAq", "dPs"),
            ("측정 정압", "mmAq", "mPs"),
            ("설계 전류", "A", "dAmp"),
            ("측정 전류", "A", "mAmp"),
            ("필터 정압손실 기준", "mmAq", "dFil"),
            ("필터 정압손실 측정", "mmAq", "mFil"),
        ],
    },
    "공기비": {
        "fields": [
            ("CO₂", "%", "co2"),
            ("O₂", "%", "o2"),
            ("CO", "%", "co"),
            ("CO 측정", "ppm", "ppmCO"),
            ("NOx 측정", "ppm", "ppmNOx"),
        ],
    },
}

PERFORMANCE_CALC_DEFAULTS = {
    ("보일러", "hv"): "10190",
}

PERFORMANCE_EQUIPMENT_TYPES = {
    "터보냉동기": "냉동기",
    "냉각탑": "냉각탑",
    "보일러": "보일러",
    "열교환기": "열교환기",
    "펌프": "펌프",
    "공기조화기": "공기조화기",
}


def numeric_or_zero(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def percentage_of_design(measured, design):
    return (measured / design * 100.0) if design else 0.0


def ratio_review(measured, design, tolerance=10.0):
    if not design:
        return "판단보류", None, 0.0
    ratio = measured / design * 100.0
    ok = (100.0 - tolerance) <= ratio <= (100.0 + tolerance)
    return ("정상" if ok else "이상"), ok, ratio


class PerformanceCalculationMixin:
    @staticmethod
    def calc_num(value):
        return numeric_or_zero(value)

    @staticmethod
    def calc_pct(measured, design):
        return percentage_of_design(measured, design)

    @staticmethod
    def calc_ratio_judge(measured, design, tolerance=10.0):
        return ratio_review(measured, design, tolerance)

    @staticmethod
    def performance_equipment_type(calc_type):
        return PERFORMANCE_EQUIPMENT_TYPES.get(calc_type, "")

    def on_performance_calc_type_changed(self, *_args):
        self.refresh_performance_calc_fields()
        self.refresh_performance_equipment_choices()

    def refresh_performance_equipment_choices(self):
        if not hasattr(self, "performance_calc_equipment"):
            return

        combo = self.performance_calc_equipment
        current_id = str(combo.currentData() or "").strip()
        calc_type = self.performance_calc_type.currentText()
        equipment_type = self.performance_equipment_type(calc_type)

        combo.blockSignals(True)
        combo.clear()
        combo.addItem("장비 미연결", "")

        if equipment_type:
            for row in range(self.equipment_register_table.rowCount()):
                data = self.register_row_data(row)
                if data.get("설비종류", "") != equipment_type:
                    continue

                subtype = str(data.get("세부유형", "") or "").strip()
                if calc_type == "터보냉동기":
                    subtype = normalize_chiller_subtype(subtype)
                    if subtype not in {"turbo", "unspecified"}:
                        continue

                management_number = data.get("관리번호", "") or "관리번호 미지정"
                label = f"{equipment_type} | {management_number}"
                if equipment_type == "냉동기":
                    subtype_label = chiller_subtype_info(subtype)["label"]
                    label += f" | {subtype_label}"
                    if calc_type == "터보냉동기" and subtype == "unspecified":
                        label += " (세부유형 확인 필요)"
                combo.addItem(label, data.get("equipment_id", ""))

        index = combo.findData(current_id) if current_id else 0
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)
        self.on_performance_equipment_changed()

    def selected_performance_equipment_data(self):
        if not hasattr(self, "performance_calc_equipment"):
            return {}
        equipment_id = str(
            self.performance_calc_equipment.currentData() or ""
        ).strip()
        if not equipment_id:
            return {}
        register_row = self.register_row_for_equipment_id(equipment_id)
        return self.register_row_data(register_row) if register_row >= 0 else {}

    def on_performance_equipment_changed(self, *_args):
        data = self.selected_performance_equipment_data()
        if data:
            self.performance_calc_tag.setText(data.get("관리번호", ""))
            self.restore_selected_performance_calculation()

    def restore_selected_performance_calculation(self):
        """Restore, never recalculate, the uniquely saved selected record."""
        if getattr(self, "_loading_saved_performance_calculation", False):
            return False
        equipment_id = str(
            self.performance_calc_equipment.currentData() or ""
        ).strip()
        calc_type = self.performance_calc_type.currentText()
        if not equipment_id or not calc_type:
            return False
        matches = self.find_performance_records_by_equipment_id(
            equipment_id, calc_type
        )
        if len(matches) != 1:
            return False
        self._populate_saved_performance_record(matches[0])
        return True

    def validate_performance_equipment_selection(self, show_message=True):
        data = self.selected_performance_equipment_data()
        if not data:
            return True

        calc_type = self.performance_calc_type.currentText()
        expected_type = self.performance_equipment_type(calc_type)
        if expected_type and data.get("설비종류", "") != expected_type:
            if show_message:
                QMessageBox.warning(
                    self, "성능계산 장비 확인", "계산종류와 선택 장비가 일치하지 않습니다."
                )
            return False

        if calc_type == "터보냉동기":
            subtype = normalize_chiller_subtype(data.get("세부유형", ""))
            if subtype != "turbo":
                if show_message:
                    QMessageBox.warning(
                        self,
                        "냉동기 세부유형 확인",
                        "터보냉동기 계산은 세부유형이 '터보냉동기'로 확인된 장비만 연결할 수 있습니다.",
                    )
                return False
        return True

    def find_performance_records_by_equipment_id(
        self, equipment_id, calc_type=""
    ):
        equipment_id = str(equipment_id or "").strip()
        if not equipment_id:
            return []
        return [
            record
            for record in getattr(self, "performance_calculations", [])
            if isinstance(record, dict)
            and str(record.get("equipment_id", "") or "").strip()
            == equipment_id
            and (not calc_type or record.get("종류", "") == calc_type)
        ]

    def get_reference_cop_for_equipment(self, equipment_id):
        equipment_id = str(equipment_id or "").strip()
        register_row = self.register_row_for_equipment_id(equipment_id)
        if register_row < 0:
            return None

        equipment = self.register_row_data(register_row)
        if equipment.get("설비종류", "") != "냉동기":
            return None
        if normalize_chiller_subtype(
            equipment.get("세부유형", "")
        ) != "turbo":
            return None

        records = self.find_performance_records_by_equipment_id(
            equipment_id, "터보냉동기"
        )
        for record in reversed(records):
            if str(record.get("핵심지표", "") or "").strip() != "COP":
                continue
            value = str(record.get("핵심값", "") or "").strip()
            if not value:
                continue
            return {
                "값": value,
                "종류": "터보냉동기",
                "equipment_id": equipment_id,
                "관리번호": equipment.get("관리번호", ""),
            }
        return None

    def current_cop_reference_apply_context(self):
        key = getattr(self, "current_detail_equipment_key", None)
        target = self.find_target_data_by_key(key) if key else None
        if not target or target.get("설비종류", "") != "냉동기":
            return None

        row = self.inspection_detail_table.currentRow()
        if row < 0:
            return None
        if (
            self.table_item_text(self.inspection_detail_table, row, 0) != "15"
            or self.table_item_text(self.inspection_detail_table, row, 1)
            != "COP 상태"
        ):
            return None

        target_id = str(target.get("equipment_id", "") or "").strip()
        if not target_id:
            return None
        register_row = self.register_row_for_equipment_id(target_id)
        if register_row < 0:
            return None
        equipment = self.register_row_data(register_row)
        if str(equipment.get("equipment_id", "") or "").strip() != target_id:
            return None
        if normalize_chiller_subtype(
            equipment.get("세부유형", "")
        ) != "turbo":
            return None

        reference = self.get_reference_cop_for_equipment(target_id)
        if not reference or reference.get("equipment_id", "") != target_id:
            return None
        return {
            "row": row,
            "target": target,
            "equipment": equipment,
            "reference": reference,
        }

    def apply_reference_cop_to_measurement(self):
        context = self.current_cop_reference_apply_context()
        if not context:
            QMessageBox.warning(
                self,
                "참고 COP 적용",
                "현재 장비·세부유형·성능계산 연결을 다시 확인하십시오.",
            )
            self.refresh_performance_cop_reference()
            return False

        row = context["row"]
        reference = context["reference"]
        equipment = context["equipment"]
        equipment_id = str(equipment.get("equipment_id", "") or "").strip()
        current_target_id = str(
            context["target"].get("equipment_id", "") or ""
        ).strip()
        current_reference = self.get_reference_cop_for_equipment(equipment_id)
        if (
            not current_reference
            or current_target_id != equipment_id
            or current_reference.get("equipment_id", "") != equipment_id
        ):
            QMessageBox.warning(
                self,
                "참고 COP 적용",
                "성능계산 정보가 변경되었거나 장비 연결이 일치하지 않아 적용을 중단했습니다.",
            )
            self.refresh_performance_cop_reference()
            return False

        value = str(current_reference.get("값", "") or "").strip()
        measured_item = self.inspection_detail_table.item(row, 6)
        if measured_item is None or not value:
            return False
        before = measured_item.text().strip()
        if before == value:
            QMessageBox.information(
                self, "참고 COP 적용", "현재 측정확인값이 참고 COP와 이미 동일합니다."
            )
            return False

        management_number = equipment.get("관리번호", "") or "관리번호 미지정"
        answer = QMessageBox.question(
            self,
            "성능계산 참고 COP 적용",
            f"장비: {management_number}\n"
            f"성능계산 참고 COP: {value}\n"
            f"현재 측정확인값: {before or '(비어 있음)'}\n"
            f"변경 후 측정확인값: {value}\n\n"
            "성능계산 참고값을 측정확인값으로 적용하시겠습니까?\n\n"
            "최종판정은 자동으로 변경되지 않습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False

        self.inspection_detail_table.blockSignals(True)
        try:
            measured_item.setText(value)
        finally:
            self.inspection_detail_table.blockSignals(False)

        try:
            self.write_audit(
                "inspection_cop_reference_applied",
                target=f"냉동기 / {management_number} / 15 COP 상태",
                field="측정확인값",
                before=before,
                after=value,
                detail=(
                    f"설비종류=냉동기 | 관리번호={management_number} | "
                    f"equipment_id={equipment_id} | 점검항목번호=15 | "
                    "점검항목=COP 상태 | 계산종류=터보냉동기"
                ),
            )
        except Exception:
            pass

        self.save_current_inspection_detail()
        self.refresh_performance_cop_reference()
        return True

    def refresh_performance_cop_reference(self):
        if not hasattr(self, "performance_cop_reference_label"):
            return

        label = self.performance_cop_reference_label
        label.clear()
        label.setVisible(False)
        self.performance_cop_reference_title.setVisible(False)
        self.apply_performance_cop_button.setVisible(False)
        self.apply_performance_cop_button.setEnabled(False)

        key = getattr(self, "current_detail_equipment_key", None)
        target = self.find_target_data_by_key(key) if key else None
        if not target or target.get("설비종류", "") != "냉동기":
            return

        has_cop_item = any(
            str(item.get("no", "")) == "15"
            and item.get("name", "") == "COP 상태"
            for item in self._inspection_db.get("냉동기", [])
        )
        if not has_cop_item:
            return

        reference = self.get_reference_cop_for_equipment(
            target.get("equipment_id", "")
        )
        if not reference:
            return

        management_number = reference.get("관리번호", "") or "관리번호 미지정"
        label.setText(
            f"{management_number} / 성능계산 참고 COP: {reference['값']} "
            "(점검항목 15 참고용 · 측정값과 최종판정은 자동 변경하지 않음)"
        )
        self.performance_cop_reference_title.setVisible(True)
        label.setVisible(True)
        apply_context = self.current_cop_reference_apply_context()
        self.apply_performance_cop_button.setVisible(apply_context is not None)
        self.apply_performance_cop_button.setEnabled(apply_context is not None)

    def reconcile_performance_calculation_equipment_ids(self):
        for record in getattr(self, "performance_calculations", []):
            if not isinstance(record, dict):
                continue

            stored_id = str(record.get("equipment_id", "") or "").strip()
            if stored_id and self.register_row_for_equipment_id(stored_id) >= 0:
                continue
            if stored_id:
                continue

            calc_type = str(record.get("종류", "") or "").strip()
            equipment_type = self.performance_equipment_type(calc_type)
            management_number = str(
                record.get("장비번호", "") or ""
            ).strip()
            if not equipment_type or not management_number:
                continue

            register_row = self.unique_register_row(
                equipment_type, management_number
            )
            if register_row < 0:
                continue
            data = self.register_row_data(register_row)
            if calc_type == "터보냉동기" and normalize_chiller_subtype(
                data.get("세부유형", "")
            ) != "turbo":
                continue

            record["equipment_id"] = data.get("equipment_id", "")
            record["설비종류"] = data.get("설비종류", "")
            record["관리번호_snapshot"] = data.get("관리번호", "")
            if data.get("세부유형", ""):
                record["세부유형_snapshot"] = data.get("세부유형", "")

    def load_saved_performance_calculation(self, row, _column=0):
        records = getattr(self, "performance_calculations", [])
        if row < 0 or row >= len(records):
            return
        record = records[row]
        if not isinstance(record, dict):
            return

        self._loading_saved_performance_calculation = True
        try:
            self.performance_calc_type.setCurrentText(record.get("종류", ""))
            equipment_id = str(record.get("equipment_id", "") or "").strip()
            index = self.performance_calc_equipment.findData(equipment_id)
            self.performance_calc_equipment.setCurrentIndex(index if index >= 0 else 0)
            if index < 0:
                self.performance_calc_tag.setText(record.get("장비번호", ""))
            self._populate_saved_performance_record(record)
        finally:
            self._loading_saved_performance_calculation = False

    def _populate_saved_performance_record(self, record):
        """Populate exact saved inputs/results without executing formulas."""
        values = record.get("입력값", {})
        for input_row in range(self.performance_calc_input_table.rowCount()):
            label_item = self.performance_calc_input_table.item(input_row, 0)
            if label_item:
                key = label_item.data(Qt.UserRole)
                self.performance_calc_input_table.item(input_row, 2).setText(
                    str(values.get(key, ""))
                )

        result_rows = [
            [
                item.get("항목", ""),
                item.get("설계기준", ""),
                item.get("값", ""),
                item.get("대비", ""),
                item.get("판정", ""),
            ]
            for item in record.get("산출결과", [])
            if isinstance(item, dict)
        ]
        self.set_performance_calc_results(result_rows, record.get("비고", ""))

    def refresh_performance_calc_fields(self):
        if not hasattr(self, "performance_calc_input_table"):
            return

        calc_type = self.performance_calc_type.currentText()
        definition = PERFORMANCE_CALC_DEFS.get(calc_type, {})
        fields = definition.get("fields", [])

        self.performance_calc_input_table.setRowCount(len(fields))

        for row, (label, unit, key) in enumerate(fields):
            label_item = QTableWidgetItem(label)
            label_item.setData(Qt.UserRole, key)
            label_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            unit_item = QTableWidgetItem(unit)
            unit_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            value = PERFORMANCE_CALC_DEFAULTS.get(
                (calc_type, key),
                ""
            )
            value_item = QTableWidgetItem(value)

            self.performance_calc_input_table.setItem(row, 0, label_item)
            self.performance_calc_input_table.setItem(row, 1, unit_item)
            self.performance_calc_input_table.setItem(row, 2, value_item)

        self.performance_calc_result_table.setRowCount(0)
        self.performance_calc_note.setText("")

    def performance_calc_values(self):
        values = {}
        for row in range(self.performance_calc_input_table.rowCount()):
            label_item = self.performance_calc_input_table.item(row, 0)
            value_item = self.performance_calc_input_table.item(row, 2)
            if not label_item:
                continue
            key = label_item.data(Qt.UserRole)
            values[key] = self.calc_num(
                value_item.text() if value_item else ""
            )
        return values

    def set_performance_calc_results(self, rows, note=""):
        self.performance_calc_result_table.setRowCount(len(rows))
        for row_index, row_data in enumerate(rows):
            for col, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                if col < 5:
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.performance_calc_result_table.setItem(
                    row_index, col, item
                )
        self.performance_calc_result_table.resizeRowsToContents()
        self.performance_calc_note.setText(note)

    def calculate_performance_metric(self):
        calc_type = self.performance_calc_type.currentText()
        v = self.performance_calc_values()
        rows = []
        note = ""

        if calc_type == "터보냉동기":
            d_dt = v.get("dIn", 0) - v.get("dOut", 0)
            m_dt = v.get("mIn", 0) - v.get("mOut", 0)
            d_evap = v.get("dCap", 0) * 3024.0
            m_cap = (
                v.get("mFlow", 0) * m_dt * 1000.0 / 3024.0
                if m_dt else 0.0
            )
            m_evap = m_cap * 3024.0
            d_comp = v.get("dPow", 0) * 860.0
            m_comp = v.get("mPow", 0) * 860.0
            d_cop = d_evap / d_comp if d_comp else 0.0
            m_cop = m_evap / m_comp if m_comp else 0.0
            load = (
                m_cap / v.get("dCap", 0) * 100.0
                if v.get("dCap", 0) else 0.0
            )
            judge = (
                "정상" if 5.5 <= m_cop <= 7.0 else "주의"
            )
            rows = [
                ["냉수 온도차(℃)", f"{d_dt:.2f}", f"{m_dt:.2f}",
                 f"{self.calc_pct(m_dt, d_dt):.1f}%" if d_dt else "-", ""],
                ["냉방능력(USRT)", f"{v.get('dCap',0):.1f}", f"{m_cap:.1f}",
                 f"{load:.1f}%", ""],
                ["부하율(%)", "100.0", f"{load:.1f}", "", ""],
                ["COP", f"{d_cop:.2f}", f"{m_cop:.2f}",
                 f"{self.calc_pct(m_cop, d_cop):.1f}%" if d_cop else "-", judge],
            ]
            note = (
                "COP 5.5~7.0은 참고용 범위입니다. 냉동기 형식·정격조건·부분부하 조건과 "
                "제조사 성능자료를 우선 적용하십시오."
            )

        elif calc_type == "냉각탑":
            d_range = v.get("dIn", 0) - v.get("dOut", 0)
            m_range = v.get("mIn", 0) - v.get("mOut", 0)
            d_app = v.get("dOut", 0) - v.get("dWB", 0)
            m_app = v.get("mOut", 0) - v.get("mWB", 0)
            d_eff = (
                d_range / (d_range + d_app) * 100.0
                if (d_range + d_app) else 0.0
            )
            m_eff = (
                m_range / (m_range + m_app) * 100.0
                if (m_range + m_app) else 0.0
            )
            judge = (
                "정상" if 55.0 <= m_eff <= 75.0 else "주의"
            )
            rows = [
                ["Cooling Range(℃)", f"{d_range:.2f}", f"{m_range:.2f}",
                 f"{self.calc_pct(m_range, d_range):.1f}%" if d_range else "-", ""],
                ["Approach(℃)", f"{d_app:.2f}", f"{m_app:.2f}",
                 f"{self.calc_pct(m_app, d_app):.1f}%" if d_app else "-", ""],
                ["유효도(%)", f"{d_eff:.1f}", f"{m_eff:.1f}",
                 f"{self.calc_pct(m_eff, d_eff):.1f}%" if d_eff else "-", judge],
            ]
            note = (
                "냉각탑 유효도는 외기 습구온도와 운전부하에 민감합니다. "
                "설계조건과 동일·유사한 조건에서 비교하는 것이 원칙입니다."
            )

        elif calc_type == "펌프":
            d_p = v.get("pDis", 0) - v.get("pSuc", 0)
            measured_head = d_p * 101.97
            jf, _, rf = self.calc_ratio_judge(
                v.get("mFlow", 0), v.get("dFlow", 0), 10.0
            )
            jh, _, rh = self.calc_ratio_judge(
                measured_head, v.get("dHead", 0), 10.0
            )
            current_ok = (
                v.get("mAmp", 0) <= v.get("dAmp", 0)
                if v.get("dAmp", 0) else None
            )
            jc = (
                "정상" if current_ok is True
                else "이상" if current_ok is False
                else "판단보류"
            )
            rows = [
                ["유량(m³/h)", f"{v.get('dFlow',0):.1f}", f"{v.get('mFlow',0):.1f}",
                 f"{rf:.1f}%" if rf else "-", jf],
                ["양정(m)", f"{v.get('dHead',0):.1f}", f"{measured_head:.1f}",
                 f"{rh:.1f}%" if rh else "-", jh],
                ["전류(A)", f"{v.get('dAmp',0):.1f}", f"{v.get('mAmp',0):.1f}",
                 f"{self.calc_pct(v.get('mAmp',0), v.get('dAmp',0)):.1f}%" if v.get('dAmp',0) else "-", jc],
            ]
            note = (
                "펌프 유량·양정은 설계값 대비 ±10%를 1차 검토기준으로 표시했습니다. "
                "실제 판정은 펌프곡선, 밸브개도, 시스템 저항 및 운전점 확인이 필요합니다."
            )

        elif calc_type == "열교환기":
            q_in = (
                v.get("p1f", 0)
                * (v.get("p1in", 0) - v.get("p1out", 0))
                * 60.0
            )
            q_out = (
                v.get("p2f", 0)
                * (v.get("p2out", 0) - v.get("p2in", 0))
                * 60.0
            )
            eff = q_out / q_in * 100.0 if q_in else 0.0
            judge = "정상" if 85.0 <= eff <= 105.0 else "주의"
            rows = [
                ["1차측 처리열량(kcal/h)", "-", f"{q_in:,.0f}", "", ""],
                ["2차측 처리열량(kcal/h)", "-", f"{q_out:,.0f}", "", ""],
                ["열교환 효율(%)", "85~105 참고", f"{eff:.2f}", "", judge],
            ]
            note = (
                "열교환 효율은 유량계·온도계 오차와 동시측정 여부의 영향을 크게 받습니다. "
                "유량·온도를 동일 시점에 측정하고 제조사 설계조건과 비교하십시오."
            )

        elif calc_type == "공기조화기":
            jsa, _, rsa = self.calc_ratio_judge(
                v.get("mSA", 0), v.get("dSA", 0), 10.0
            )
            jra, _, rra = self.calc_ratio_judge(
                v.get("mRA", 0), v.get("dRA", 0), 10.0
            )
            filter_ok = (
                v.get("mFil", 0) <= v.get("dFil", 0)
                if v.get("dFil", 0) else None
            )
            jf = (
                "정상" if filter_ok is True
                else "이상" if filter_ok is False
                else "판단보류"
            )
            rows = [
                ["급기풍량(CMH)", f"{v.get('dSA',0):,.0f}", f"{v.get('mSA',0):,.0f}",
                 f"{rsa:.1f}%" if rsa else "-", jsa],
                ["환기풍량(CMH)", f"{v.get('dRA',0):,.0f}", f"{v.get('mRA',0):,.0f}",
                 f"{rra:.1f}%" if rra else "-", jra],
                ["정압(mmAq)", f"{v.get('dPs',0):.1f}", f"{v.get('mPs',0):.1f}",
                 f"{self.calc_pct(v.get('mPs',0), v.get('dPs',0)):.1f}%" if v.get('dPs',0) else "-", ""],
                ["전류(A)", f"{v.get('dAmp',0):.1f}", f"{v.get('mAmp',0):.1f}",
                 f"{self.calc_pct(v.get('mAmp',0), v.get('dAmp',0)):.1f}%" if v.get('dAmp',0) else "-", ""],
                ["필터 정압손실(mmAq)", f"{v.get('dFil',0):.1f}", f"{v.get('mFil',0):.1f}",
                 "", jf],
            ]
            note = (
                "공기조화기 풍량은 설계값 대비 ±10%를 1차 검토기준으로 표시합니다. "
                "댐퍼개도, 필터차압, 회전수, VAV/CAV 조건을 함께 확인하십시오."
            )

        elif calc_type == "공기비":
            co2 = v.get("co2", 0)
            o2 = v.get("o2", 0)
            co = v.get("co", 0)
            n2 = 100.0 - (co2 + o2 + co)
            co2max = (21.0 * co2 / (21.0 - o2)) if (21.0 - o2) else 0.0
            ratio = co2max / co2 if co2 else 0.0
            corr = ((21.0 / (21.0 - o2)) / (21.0 / 17.0)) if (21.0 - o2) else 0.0
            judge = "정상" if 1.0 <= ratio <= 1.3 else "주의"
            rows = [
                ["N₂값(%)", "-", f"{n2:.2f}", "", ""],
                ["CO₂max(%)", "-", f"{co2max:.2f}", "", ""],
                ["공기비", "1.0~1.3 참고", f"{ratio:.3f}", "", judge],
                ["O₂ 4% 보정계수", "-", f"{corr:.3f}", "", ""],
                ["CO 보정값(ppm)", "-", f"{v.get('ppmCO',0)*corr:.1f}", "", ""],
                ["NOx 보정값(ppm)", "-", f"{v.get('ppmNOx',0)*corr:.1f}", "", ""],
            ]
            note = (
                "공기비는 연료종류·버너형식·설치시기 및 적용 배출기준에 따라 별도 검토가 필요합니다."
            )

        elif calc_type == "보일러":
            fw = v.get("fw", 0)
            minutes = v.get("minutes", 0)
            gas = v.get("gas", 0)
            steam_t = v.get("steamT", 0)
            steam_kg = v.get("steamKg", 0)
            rated = v.get("rated", 0)
            hv = v.get("hv", 0) or 10190.0

            # 단순 포화증기 엔탈피 근사값
            # 100~180℃ 범위에서 보고서 예비검토용으로 사용
            steam_h_kcal = 639.0 + max(0.0, steam_t - 100.0) * 0.35
            useful = steam_kg * max(0.0, steam_h_kcal - fw)
            fuel = gas * hv
            eff = useful / fuel * 100.0 if fuel else 0.0
            equivalent_evap = (
                useful / 539.0 * 60.0 / minutes
                if minutes else 0.0
            )
            load = (
                equivalent_evap / rated * 100.0
                if rated else 0.0
            )
            judge = "정상" if 80.0 <= eff <= 100.0 else "주의"
            rows = [
                ["추정 증기엔탈피(kcal/kg)", "-", f"{steam_h_kcal:.1f}", "", ""],
                ["출열(kcal)", "-", f"{useful:,.0f}", "", ""],
                ["입열(kcal/h)", "-", f"{fuel:,.0f}", "", ""],
                ["상당증발량(kg/h)", "-", f"{equivalent_evap:.1f}", "", ""],
                ["부하율(%)", "-", f"{load:.1f}", "", ""],
                ["보일러 운전효율(%)", "80 이상 참고", f"{eff:.2f}", "", judge],
            ]
            note = (
                "보일러 계산은 입력자료의 기준시간을 반드시 일치시켜야 합니다. "
                "증기엔탈피는 예비검토용 근사값이므로 최종 보고서에서는 압력·온도에 따른 "
                "정확한 증기표 값을 적용하십시오."
            )

        self.set_performance_calc_results(rows, note)
        return rows

    def clear_performance_calc_inputs(self):
        self.refresh_performance_calc_fields()
        self.performance_calc_equipment.setCurrentIndex(0)
        self.performance_calc_tag.clear()

    def performance_calc_core_metric(self):
        calc_type = self.performance_calc_type.currentText()
        preferred = {
            "터보냉동기": "COP",
            "냉각탑": "유효도",
            "보일러": "보일러 운전효율",
            "열교환기": "열교환 효율",
            "펌프": "유량",
            "공기조화기": "급기풍량",
            "공기비": "공기비",
        }.get(calc_type, "")

        for row in range(self.performance_calc_result_table.rowCount()):
            metric = self.table_item_text(
                self.performance_calc_result_table, row, 0
            )
            if preferred and preferred.lower() in metric.lower():
                return {
                    "지표": metric,
                    "값": self.table_item_text(
                        self.performance_calc_result_table, row, 2
                    ),
                    "판정": self.table_item_text(
                        self.performance_calc_result_table, row, 4
                    ),
                }

        if self.performance_calc_result_table.rowCount():
            return {
                "지표": self.table_item_text(
                    self.performance_calc_result_table, 0, 0
                ),
                "값": self.table_item_text(
                    self.performance_calc_result_table, 0, 2
                ),
                "판정": self.table_item_text(
                    self.performance_calc_result_table, 0, 4
                ),
            }

        return {"지표": "", "값": "", "판정": ""}

    def save_performance_calculation(self):
        if self.performance_calc_result_table.rowCount() == 0:
            self.calculate_performance_metric()

        if self.performance_calc_result_table.rowCount() == 0:
            return

        calc_type = self.performance_calc_type.currentText()
        tag = self.performance_calc_tag.text().strip()
        equipment_data = self.selected_performance_equipment_data()
        if equipment_data and not self.validate_performance_equipment_selection():
            return
        core = self.performance_calc_core_metric()

        review_status = core.get("판정", "")
        review_note = self.performance_calc_note.text()

        if review_status in {"이상", "주의"}:
            review_note = (
                "[불합격 검토 필요] 성능계산에서 기준 이탈 또는 주의값이 확인됨. "
                "운전조건·부하율·제조사 기준·계측오차를 검토한 후 4-3 점검표에서 "
                "책임기술자가 최종 ○ 합격 / X 불합격을 확정하십시오. "
                + review_note
            )

        record = {
            "종류": calc_type,
            "장비번호": tag,
            "입력값": self.performance_calc_values(),
            "산출결과": [
                {
                    "항목": self.table_item_text(
                        self.performance_calc_result_table, row, 0
                    ),
                    "설계기준": self.table_item_text(
                        self.performance_calc_result_table, row, 1
                    ),
                    "값": self.table_item_text(
                        self.performance_calc_result_table, row, 2
                    ),
                    "대비": self.table_item_text(
                        self.performance_calc_result_table, row, 3
                    ),
                    "판정": self.table_item_text(
                        self.performance_calc_result_table, row, 4
                    ),
                }
                for row in range(
                    self.performance_calc_result_table.rowCount()
                )
            ],
            "핵심지표": core.get("지표", ""),
            "핵심값": core.get("값", ""),
            "판정": review_status,
            "비고": review_note,
        }
        if equipment_data:
            record["equipment_id"] = equipment_data.get("equipment_id", "")
            record["설비종류"] = equipment_data.get("설비종류", "")
            record["관리번호_snapshot"] = equipment_data.get("관리번호", "")
            if equipment_data.get("세부유형", ""):
                record["세부유형_snapshot"] = equipment_data.get(
                    "세부유형", ""
                )

        replaced = False
        for index, old in enumerate(self.performance_calculations):
            same_record = False
            if equipment_data:
                same_record = (
                    old.get("종류") == calc_type
                    and old.get("equipment_id") == equipment_data.get("equipment_id")
                )
            elif not old.get("equipment_id"):
                same_record = (
                    old.get("종류") == calc_type
                    and old.get("장비번호") == tag
                )
            if same_record:
                self.performance_calculations[index] = record
                replaced = True
                break

        if not replaced:
            self.performance_calculations.append(record)

        self.refresh_saved_performance_calculations()
        self.refresh_performance_cop_reference()
        self.status_label.setText(
            f"{calc_type} {tag or ''} 성능계산 결과를 저장했습니다."
        )

    def refresh_saved_performance_calculations(self):
        if not hasattr(self, "performance_calc_saved_table"):
            return

        rows = getattr(self, "performance_calculations", [])
        self.performance_calc_saved_table.setRowCount(len(rows))

        for row, record in enumerate(rows):
            display_tag = record.get("장비번호", "")
            equipment_id = str(record.get("equipment_id", "") or "").strip()
            register_row = self.register_row_for_equipment_id(equipment_id)
            if register_row >= 0:
                display_tag = self.register_row_data(register_row).get(
                    "관리번호", display_tag
                )
            values = [
                record.get("종류", ""),
                display_tag,
                record.get("핵심지표", ""),
                record.get("핵심값", ""),
                record.get("판정", ""),
                record.get("비고", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.performance_calc_saved_table.setItem(row, col, item)

        self.performance_calc_saved_table.resizeRowsToContents()
