import re
import shutil
import subprocess
import uuid
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QGridLayout,
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

from .helpers import (
    equipment_folder_name,
    photo_file_stem,
    safe_photo_name,
)


class PhotoManagerMixin:
    def create_photo_page(self):
        page = QWidget()
        root = QVBoxLayout(page)

        title = QLabel("5. 사진관리")
        title.setStyleSheet("font-size: 21px; font-weight: bold;")
        root.addWidget(title)

        notice = QLabel(
            "사진을 점검대상 장비와 점검항목에 연결합니다. "
            "전체사진·명판사진·측정사진·결함사진을 구분하면 보고서 작성 시 자동 배치할 수 있습니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding: 8px; background: #eef6ff; border: 1px solid #8bb8e8;"
        )
        root.addWidget(notice)

        selection_layout = QGridLayout()

        self.photo_equipment_combo = QComboBox()
        self.photo_equipment_combo.currentIndexChanged.connect(
            self.on_photo_equipment_changed
        )

        self.photo_item_combo = QComboBox()
        self.photo_type_combo = QComboBox()
        self.photo_type_combo.addItems(
            [
                "장비 전체사진",
                "명판사진",
                "점검사진",
                "측정사진",
                "결함사진",
                "조치 후 사진",
                "기타",
            ]
        )

        selection_layout.addWidget(QLabel("점검대상 장비"), 0, 0)
        selection_layout.addWidget(self.photo_equipment_combo, 0, 1)
        selection_layout.addWidget(QLabel("연결 점검항목"), 0, 2)
        selection_layout.addWidget(self.photo_item_combo, 0, 3)
        selection_layout.addWidget(QLabel("사진 구분"), 1, 0)
        selection_layout.addWidget(self.photo_type_combo, 1, 1)

        refresh_equipment_button = QPushButton("점검대상 새로고침")
        refresh_equipment_button.clicked.connect(
            self.populate_photo_equipment_combo
        )

        add_button = QPushButton("사진 추가")
        add_button.clicked.connect(self.add_photos)

        selection_layout.addWidget(refresh_equipment_button, 1, 2)
        selection_layout.addWidget(add_button, 1, 3)

        root.addLayout(selection_layout)

        body = QHBoxLayout()

        left = QVBoxLayout()
        self.photo_table = QTableWidget()
        self.photo_table.setColumnCount(6)
        self.photo_table.setHorizontalHeaderLabels(
            [
                "장비",
                "점검항목",
                "사진구분",
                "파일명",
                "설명",
                "파일경로",
            ]
        )
        self.photo_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )
        self.photo_table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )
        self.photo_table.verticalHeader().setVisible(False)
        self.photo_table.setAlternatingRowColors(True)
        self.photo_table.itemSelectionChanged.connect(
            self.on_photo_row_selected
        )

        photo_header = self.photo_table.horizontalHeader()
        photo_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        photo_header.setSectionResizeMode(1, QHeaderView.Stretch)
        photo_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        photo_header.setSectionResizeMode(3, QHeaderView.Stretch)
        photo_header.setSectionResizeMode(4, QHeaderView.Stretch)
        photo_header.setSectionResizeMode(5, QHeaderView.Stretch)

        left.addWidget(self.photo_table)

        photo_buttons = QHBoxLayout()
        remove_button = QPushButton("선택 사진 삭제")
        open_folder_button = QPushButton("사진 저장폴더 열기")
        remove_button.clicked.connect(self.remove_selected_photo)
        open_folder_button.clicked.connect(self.open_photo_storage_folder)

        photo_buttons.addWidget(remove_button)
        photo_buttons.addWidget(open_folder_button)
        photo_buttons.addStretch()
        left.addLayout(photo_buttons)

        body.addLayout(left, 3)

        right = QVBoxLayout()

        self.photo_preview = QLabel("사진을 선택하십시오.")
        self.photo_preview.setAlignment(Qt.AlignCenter)
        self.photo_preview.setMinimumSize(QSize(360, 300))
        self.photo_preview.setStyleSheet(
            "border: 1px solid #aaaaaa; background: #fafafa;"
        )
        right.addWidget(self.photo_preview)

        right.addWidget(QLabel("사진 설명"))
        self.photo_caption_edit = QPlainTextEdit()
        self.photo_caption_edit.setPlaceholderText(
            "예: P-03 냉수순환펌프 명판, 진동 측정 상태, 누수 발생 부위"
        )
        self.photo_caption_edit.setMaximumHeight(110)
        right.addWidget(self.photo_caption_edit)

        save_caption_button = QPushButton("사진 설명 저장")
        save_caption_button.clicked.connect(self.save_photo_caption)
        right.addWidget(save_caption_button)
        right.addStretch()

        body.addLayout(right, 2)
        root.addLayout(body, 1)

        self.photo_summary = QLabel("등록 사진 0장")
        self.photo_summary.setStyleSheet(
            "padding: 7px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        root.addWidget(self.photo_summary)

        shot_group = QTabWidget()
        shot_tab = QWidget()
        shot_layout = QVBoxLayout(shot_tab)

        shot_buttons = QHBoxLayout()
        make_shot_button = QPushButton("촬영목록 생성·새로고침")
        make_shot_button.clicked.connect(
            self.refresh_shot_checklist
        )
        save_shot_button = QPushButton("촬영목록 TXT 저장")
        save_shot_button.clicked.connect(
            self.save_shot_checklist
        )
        shot_buttons.addWidget(make_shot_button)
        shot_buttons.addWidget(save_shot_button)
        shot_buttons.addStretch()
        shot_layout.addLayout(shot_buttons)

        self.shot_checklist_preview = QPlainTextEdit()
        self.shot_checklist_preview.setReadOnly(True)
        self.shot_checklist_preview.setPlaceholderText(
            "점검대상 선정 후 촬영목록을 생성하십시오."
        )
        self.shot_checklist_preview.setMaximumHeight(220)
        shot_layout.addWidget(self.shot_checklist_preview)

        shot_group.addTab(shot_tab, "현장 촬영목록")

        # 촬영목록과 직접 연결되는 사진 등록표
        slot_tab = QWidget()
        slot_layout = QVBoxLayout(slot_tab)

        slot_notice = QLabel(
            "현장 촬영목록의 각 항목별로 사진을 바로 등록합니다. "
            "장비별 필수사진·측정사진·결함사진이 자동으로 생성되며 "
            "등록 여부를 한눈에 확인할 수 있습니다."
        )
        slot_notice.setWordWrap(True)
        slot_notice.setStyleSheet(
            "padding: 7px; background: #eefbf2; border: 1px solid #9bc9a7;"
        )
        slot_layout.addWidget(slot_notice)

        slot_buttons = QHBoxLayout()

        slot_refresh = QPushButton("사진목록표 생성·새로고침")
        slot_refresh.clicked.connect(self.refresh_photo_slot_table)

        folder_make = QPushButton("현장 촬영폴더 만들기")
        folder_make.clicked.connect(self.create_field_photo_folders)

        folder_import = QPushButton("촬영사진 폴더 일괄 불러오기")
        folder_import.clicked.connect(self.import_field_photo_folder)

        slot_buttons.addWidget(slot_refresh)
        slot_buttons.addWidget(folder_make)
        slot_buttons.addWidget(folder_import)
        slot_buttons.addStretch()
        slot_layout.addLayout(slot_buttons)

        workflow_notice = QLabel(
            "권장순서: ① 촬영목록 생성 → ② 현장 촬영폴더 만들기 → "
            "③ 생성된 장비별 폴더와 촬영명에 맞춰 사진 저장 → "
            "④ 촬영사진 폴더 일괄 불러오기"
        )
        workflow_notice.setWordWrap(True)
        workflow_notice.setStyleSheet(
            "padding: 7px; background: #eef6ff; border: 1px solid #9ec5e5;"
        )
        slot_layout.addWidget(workflow_notice)

        self.photo_slot_table = QTableWidget(0, 6)
        self.photo_slot_table.setHorizontalHeaderLabels(
            ["점검대상 장비", "촬영항목", "등록상태", "등록파일", "사진 추가", "미리보기"]
        )
        self.photo_slot_table.verticalHeader().setVisible(False)
        self.photo_slot_table.setAlternatingRowColors(True)
        slot_header = self.photo_slot_table.horizontalHeader()
        slot_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        slot_header.setSectionResizeMode(1, QHeaderView.Stretch)
        slot_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        slot_header.setSectionResizeMode(3, QHeaderView.Stretch)
        slot_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        slot_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        slot_layout.addWidget(self.photo_slot_table)

        self.photo_slot_summary = QLabel("촬영목록표 미생성")
        self.photo_slot_summary.setStyleSheet(
            "padding: 7px; background: #f8fafc; border: 1px solid #d1d5db;"
        )
        slot_layout.addWidget(self.photo_slot_summary)

        shot_group.addTab(slot_tab, "촬영목록 연동 사진등록")
        root.addWidget(shot_group)

        bottom = QHBoxLayout()
        previous_button = QPushButton("이전: 점검결과")
        previous_button.setMinimumHeight(40)
        previous_button.clicked.connect(
            lambda: self.menu.setCurrentRow(3)
        )

        next_button = QPushButton("다음: 시스템 검토")
        next_button.setMinimumHeight(40)
        next_button.clicked.connect(
            lambda: self.menu.setCurrentRow(5)
        )

        bottom.addWidget(previous_button)
        bottom.addStretch()
        bottom.addWidget(next_button)
        root.addLayout(bottom)

        return page


    def valid_photo_target_rows(self):
        valid_rows = []

        for row in range(self.target_table.rowCount()):
            source_combo = self.target_table.cellWidget(row, 2)

            if not source_combo:
                continue

            register_row = source_combo.currentData()

            if register_row in (None, -1):
                continue

            valid_rows.append(row)

        return valid_rows

    def populate_photo_equipment_combo(self):
        if not hasattr(self, "photo_equipment_combo"):
            return

        previous_row = self.photo_equipment_combo.currentData()

        self.photo_equipment_combo.blockSignals(True)
        self.photo_equipment_combo.clear()

        valid_rows = self.valid_photo_target_rows()

        for target_row in valid_rows:
            target = self.target_row_data(target_row)
            label = (
                f"{target['설비종류']} | 점검번호 {target['점검번호']} | "
                f"{target.get('관리번호', '') or '관리번호 미선택'}"
            )
            self.photo_equipment_combo.addItem(label, target_row)

        if previous_row is not None:
            index = self.photo_equipment_combo.findData(previous_row)
            if index >= 0:
                self.photo_equipment_combo.setCurrentIndex(index)

        self.photo_equipment_combo.blockSignals(False)

        if self.photo_equipment_combo.count() > 0:
            if self.photo_equipment_combo.currentIndex() < 0:
                self.photo_equipment_combo.setCurrentIndex(0)

            self.on_photo_equipment_changed(
                self.photo_equipment_combo.currentIndex()
            )
        else:
            self.photo_item_combo.clear()
            self.photo_item_combo.addItem("점검대상이 없습니다.")

    def on_photo_equipment_changed(self, index):
        self.photo_item_combo.clear()
        self.photo_item_combo.addItem("공통·장비 전체")

        target_row = self.photo_equipment_combo.itemData(index)

        if target_row is None:
            return

        try:
            target_row = int(target_row)
        except (TypeError, ValueError):
            return

        if target_row < 0 or target_row >= self.target_table.rowCount():
            return

        target = self.target_row_data(target_row)
        equipment_type = target.get("설비종류", "")

        saved_results = self.inspection_results.get(
            self.target_key_from_row(target_row), []
        )

        if saved_results:
            for item in saved_results:
                number = item.get("번호", "")
                name = item.get("점검내용", "")
                self.photo_item_combo.addItem(
                    f"{number}. {name}".strip(". ")
                )
            return

        for item in self._photo_inspection_db.get(equipment_type, []):
            self.photo_item_combo.addItem(
                f"{item['no']}. {item['name']}"
            )

    @staticmethod
    def field_photo_safe_name(text, max_length=72):
        return safe_photo_name(text, max_length=max_length)

    def grouped_photo_slots(self):
        grouped = {}
        order = []

        for slot in self.required_photo_slots():
            key = slot.get("장비키", "")
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(slot)

        return [(key, grouped[key]) for key in order]

    def field_photo_equipment_folder_name(self, slots, equipment_index):
        slot = slots[0]
        target = self.target_row_data(
            int(slot.get("점검대상행", 0))
        )
        return equipment_folder_name(
            target,
            slot,
            equipment_index,
        )

    def field_photo_file_stem(self, slot_index, slot):
        return photo_file_stem(slot_index, slot)

    def create_field_photo_folders(self):
        groups = self.grouped_photo_slots()

        if not groups:
            QMessageBox.information(
                self,
                "현장 촬영폴더",
                "먼저 점검대상 설비를 선정하고 촬영목록을 생성하십시오.",
            )
            return

        remembered = self.settings.value(
            "last_field_photo_directory",
            str(Path.cwd()),
            type=str,
        )
        if not remembered or not Path(remembered).exists():
            remembered = str(Path.cwd())

        base_dir = QFileDialog.getExistingDirectory(
            self,
            "현장 촬영폴더를 만들 위치 선택",
            remembered,
        )
        if not base_dir:
            return

        site_name = self.field_photo_safe_name(
            self.site_name.text().strip() or "현장미지정"
        )
        root = Path(base_dir) / f"{site_name}_성능점검_현장사진"
        root.mkdir(parents=True, exist_ok=True)

        master_lines = [
            "기계설비 성능점검 현장 촬영목록",
            "=" * 72,
            f"현장명: {self.site_name.text().strip()}",
            "",
            "사용방법",
            "1. 장비별 폴더 안의 _촬영목록.txt를 확인합니다.",
            "2. 사진 파일명 앞 번호와 촬영명을 유지해 저장합니다.",
            "3. 같은 항목 사진이 여러 장이면 파일명 끝에 _01, _02를 붙입니다.",
            "4. 촬영 완료 후 프로그램에서 최상위 현장사진 폴더를 일괄 불러옵니다.",
            "",
        ]

        for equipment_index, (_, slots) in enumerate(groups, start=1):
            if not slots:
                continue

            folder_name = self.field_photo_equipment_folder_name(
                slots,
                equipment_index,
            )
            folder = root / folder_name
            folder.mkdir(parents=True, exist_ok=True)

            equipment_lines = [
                f"장비: {slots[0].get('장비표시', '')}",
                "",
                "권장 사진 파일명",
                "-" * 60,
            ]

            for slot_index, slot in enumerate(slots, start=1):
                stem = self.field_photo_file_stem(
                    slot_index,
                    slot,
                )
                equipment_lines.append(
                    f"{stem}.jpg    ← {slot.get('촬영항목', '')}"
                )
                master_lines.append(
                    f"{folder_name}\\{stem}.jpg"
                )

            (folder / "_촬영목록.txt").write_text(
                "\n".join(equipment_lines),
                encoding="utf-8-sig",
            )
            master_lines.append("")

        (root / "_전체촬영목록.txt").write_text(
            "\n".join(master_lines),
            encoding="utf-8-sig",
        )

        self.last_field_photo_directory = str(root)
        self.settings.setValue(
            "last_field_photo_directory",
            str(root),
        )
        self.settings.sync()

        QMessageBox.information(
            self,
            "현장 촬영폴더 생성 완료",
            "장비별 폴더와 촬영명 목록을 생성했습니다.\n\n"
            f"{root}\n\n"
            "사진 촬영 후 이 최상위 폴더를 '촬영사진 폴더 일괄 불러오기'로 선택하십시오.",
        )

    def find_photo_slots_for_folder(self, folder_name, groups):
        safe_folder = self.field_photo_safe_name(
            folder_name
        ).lower()

        # 프로그램 생성 폴더의 앞 번호를 최우선으로 사용
        number_match = re.match(r"^(\d{1,3})_", safe_folder)
        if number_match:
            index = int(number_match.group(1)) - 1
            if 0 <= index < len(groups):
                return groups[index][1]

        best_slots = None
        best_score = 0

        for _, slots in groups:
            if not slots:
                continue

            target = self.target_row_data(
                int(slots[0].get("점검대상행", 0))
            )
            candidates = [
                target.get("설비종류", ""),
                target.get("관리번호", ""),
                target.get("점검번호", ""),
            ]

            score = 0
            for candidate in candidates:
                key = self.field_photo_safe_name(
                    candidate
                ).lower()
                if key and key != "미지정" and key in safe_folder:
                    score += len(key)

            if score > best_score:
                best_score = score
                best_slots = slots

        return best_slots

    def match_photo_file_to_slot(self, file_path, slots):
        stem = file_path.stem

        # 파일명 01_, 02_ 등의 순번이 가장 정확한 매칭 기준
        match = re.match(r"^\s*(\d{1,3})[_\-\s]", stem)
        if match:
            index = int(match.group(1)) - 1
            if 0 <= index < len(slots):
                return slots[index]

        safe_stem = self.field_photo_safe_name(stem).lower()
        best = None
        best_score = 0

        for slot in slots:
            label = self.field_photo_safe_name(
                slot.get("촬영항목", "")
            ).lower()
            if label and label in safe_stem and len(label) > best_score:
                best = slot
                best_score = len(label)

        return best

    def import_field_photo_folder(self):
        groups = self.grouped_photo_slots()

        if not groups:
            QMessageBox.information(
                self,
                "촬영사진 폴더 불러오기",
                "먼저 점검대상 설비와 촬영목록을 생성하십시오.",
            )
            return

        remembered = self.settings.value(
            "last_field_photo_directory",
            str(Path.cwd()),
            type=str,
        )
        if not remembered or not Path(remembered).exists():
            remembered = str(Path.cwd())

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            "현장사진 최상위 폴더 또는 장비 폴더 선택",
            remembered,
        )
        if not selected_dir:
            return

        selected_path = Path(selected_dir)
        self.last_field_photo_directory = str(selected_path)
        self.settings.setValue(
            "last_field_photo_directory",
            str(selected_path),
        )
        self.settings.sync()

        extensions = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

        folder_jobs = []
        direct_slots = self.find_photo_slots_for_folder(
            selected_path.name,
            groups,
        )
        direct_images = [
            p for p in selected_path.iterdir()
            if p.is_file() and p.suffix.lower() in extensions
        ]

        if direct_slots and direct_images:
            folder_jobs.append((selected_path, direct_slots))
        else:
            for child in selected_path.iterdir():
                if not child.is_dir():
                    continue
                slots = self.find_photo_slots_for_folder(
                    child.name,
                    groups,
                )
                if slots:
                    folder_jobs.append((child, slots))

        if not folder_jobs:
            QMessageBox.warning(
                self,
                "촬영사진 폴더 인식 실패",
                "장비 폴더를 점검대상과 연결하지 못했습니다.\n\n"
                "프로그램의 '현장 촬영폴더 만들기'에서 만든 폴더명을 그대로 사용하십시오.",
            )
            return

        try:
            storage = self.photo_storage_dir()
        except OSError as error:
            QMessageBox.critical(
                self,
                "사진 저장폴더 오류",
                str(error),
            )
            return

        existing = {
            (
                record.get("장비키", ""),
                record.get("원본파일명", ""),
                record.get("촬영목록항목", ""),
            )
            for record in self.photo_records
        }

        imported = 0
        duplicates = 0
        unmatched = []

        for folder, slots in folder_jobs:
            images = sorted(
                [
                    p for p in folder.iterdir()
                    if p.is_file() and p.suffix.lower() in extensions
                ],
                key=lambda p: p.name.lower(),
            )

            for image_path in images:
                slot = self.match_photo_file_to_slot(
                    image_path,
                    slots,
                )
                if not slot:
                    unmatched.append(
                        f"{folder.name}\\{image_path.name}"
                    )
                    continue

                duplicate_key = (
                    slot.get("장비키", ""),
                    image_path.name,
                    slot.get("촬영항목", ""),
                )
                if duplicate_key in existing:
                    duplicates += 1
                    continue

                target_row = int(
                    slot.get("점검대상행", 0)
                )
                target = self.target_row_data(target_row)

                extension = image_path.suffix.lower() or ".jpg"
                stored_path = storage / (
                    f"{uuid.uuid4().hex}{extension}"
                )

                try:
                    shutil.copy2(image_path, stored_path)
                except OSError:
                    unmatched.append(
                        f"{folder.name}\\{image_path.name}"
                    )
                    continue

                self.photo_records.append(
                    {
                        "사진ID": uuid.uuid4().hex,
                        "장비키": slot.get("장비키", ""),
                        "점검대상행": target_row,
                        "설비종류": target.get("설비종류", ""),
                        "점검번호": target.get("점검번호", ""),
                        "관리번호": target.get("관리번호", ""),
                        "장비표시": slot.get("장비표시", ""),
                        "점검항목": slot.get("점검항목", ""),
                        "사진구분": slot.get("사진구분", ""),
                        "촬영목록항목": slot.get("촬영항목", ""),
                        "원본파일명": image_path.name,
                        "원본폴더": str(folder),
                        "저장경로": str(stored_path),
                        "설명": slot.get("촬영항목", ""),
                    }
                )

                existing.add(duplicate_key)
                imported += 1

        self.refresh_photo_table()
        self.refresh_photo_slot_table()
        self.refresh_shot_checklist()

        result = f"자동 등록 {imported}장"
        if duplicates:
            result += f" | 중복 제외 {duplicates}장"
        if unmatched:
            result += f" | 연결 실패 {len(unmatched)}장"

        self.status_label.setText(result)

        if unmatched:
            sample = "\n".join(unmatched[:12])
            QMessageBox.warning(
                self,
                "사진 일괄등록 결과",
                result + "\n\n자동 연결 실패 파일:\n" + sample,
            )
        else:
            QMessageBox.information(
                self,
                "사진 일괄등록 완료",
                result,
            )

    def required_photo_slots(self):
        """점검대상별 필수 촬영항목 목록을 생성한다."""
        self.save_current_inspection_detail()
        slots = []

        for row in range(self.target_table.rowCount()):
            target = self.target_row_data(row)
            equipment_name = target.get("설비종류", "")
            equipment_key = self.target_key_from_row(row)
            inspection_number = target.get("점검번호", "")
            management_number = target.get("관리번호", "")

            requirements = list(
                self._photo_requirements_by_equipment.get(
                    equipment_name,
                    self._photo_base_requirements,
                )
            )

            for item in self._photo_inspection_db.get(equipment_name, []):
                item_name = item.get("name", "")

                # 문서·점검표 등 항목별 필수 증빙사진
                for evidence_photo in self._photo_requirements_by_inspection_item.get(
                    item_name,
                    [],
                ):
                    label = f"증빙사진: {evidence_photo}"
                    if label not in requirements:
                        requirements.append(label)

                if self.is_measurement_item(item):
                    label = f"측정사진: {item_name}"
                    if label not in requirements:
                        requirements.append(label)

            saved_results = self.inspection_results.get(
                equipment_key,
                [],
            )
            failed_items = [
                item
                for item in saved_results
                if self.is_final_fail(item.get("판정"))
            ]

            for failed_item in failed_items:
                failed_name = failed_item.get("점검내용", "")

                # 유지관리 점검표 등 문서성 항목은 '결함사진'보다
                # 미작성/미보유 상태가 식별되는 증빙사진을 사용
                if failed_name in self._photo_requirements_by_inspection_item:
                    continue

                label = f"결함사진: {failed_name}"
                if label not in requirements:
                    requirements.append(label)

            equipment_label = (
                f"{equipment_name} / 점검 {inspection_number}"
                f" / {management_number or '관리번호 미지정'}"
            )

            for requirement in requirements:
                if requirement.startswith("측정사진:"):
                    photo_type = "측정사진"
                    inspection_item = requirement.split(":", 1)[1].strip()
                elif requirement.startswith("증빙사진:"):
                    photo_type = "증빙사진"
                    inspection_item = requirement.split(":", 1)[1].strip()
                elif requirement.startswith("결함사진:"):
                    photo_type = "결함사진"
                    inspection_item = requirement.split(":", 1)[1].strip()
                else:
                    photo_type = requirement
                    inspection_item = requirement

                slots.append(
                    {
                        "점검대상행": row,
                        "장비키": equipment_key,
                        "설비종류": equipment_name,
                        "장비표시": equipment_label,
                        "촬영항목": requirement,
                        "사진구분": photo_type,
                        "점검항목": inspection_item,
                    }
                )

        return slots

    def photo_records_for_slot(self, slot):
        matches = []
        for record in self.photo_records:
            if record.get("장비키") != slot.get("장비키"):
                continue

            if slot["사진구분"] in {"측정사진", "증빙사진", "결함사진"}:
                if (
                    record.get("사진구분") == slot["사진구분"]
                    and (
                        slot["점검항목"] in record.get("점검항목", "")
                        or slot.get("촬영항목", "") == record.get("촬영목록항목", "")
                    )
                ):
                    matches.append(record)
            else:
                if record.get("사진구분") == slot["사진구분"]:
                    matches.append(record)

        return matches

    def refresh_photo_slot_table(self):
        if not hasattr(self, "photo_slot_table"):
            return

        slots = self.required_photo_slots()
        self.photo_slot_table.setRowCount(len(slots))

        complete = 0
        for row, slot in enumerate(slots):
            records = self.photo_records_for_slot(slot)
            if records:
                complete += 1

            equipment_item = QTableWidgetItem(slot["장비표시"])
            equipment_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            equipment_item.setData(Qt.UserRole, slot)

            requirement_item = QTableWidgetItem(slot["촬영항목"])
            requirement_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            status_item = QTableWidgetItem(
                f"완료 {len(records)}장" if records else "미등록"
            )
            status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            file_names = ", ".join(
                record.get("원본파일명", "")
                for record in records
            )
            file_item = QTableWidgetItem(file_names)
            file_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            self.photo_slot_table.setItem(row, 0, equipment_item)
            self.photo_slot_table.setItem(row, 1, requirement_item)
            self.photo_slot_table.setItem(row, 2, status_item)
            self.photo_slot_table.setItem(row, 3, file_item)

            add_button = QPushButton("사진 추가")
            add_button.clicked.connect(
                lambda checked=False, r=row: self.add_photo_to_slot(r)
            )
            self.photo_slot_table.setCellWidget(row, 4, add_button)

            preview_button = QPushButton(
                "보기" if records else "-"
            )
            preview_button.setEnabled(bool(records))
            preview_button.clicked.connect(
                lambda checked=False, r=row: self.preview_photo_slot(r)
            )
            self.photo_slot_table.setCellWidget(row, 5, preview_button)

        self.photo_slot_summary.setText(
            f"촬영항목 {len(slots)}건 | 완료 {complete}건 | "
            f"미등록 {len(slots) - complete}건"
        )

    def add_photo_to_slot(self, row):
        item = self.photo_slot_table.item(row, 0)
        if item is None:
            return

        slot = item.data(Qt.UserRole)
        if not isinstance(slot, dict):
            return

        initial_folder = self.last_photo_source_dir
        if not Path(initial_folder).exists():
            initial_folder = str(Path.home())

        files, _ = QFileDialog.getOpenFileNames(
            self,
            f"{slot['장비표시']} - {slot['촬영항목']} 사진 선택",
            initial_folder,
            "이미지 파일 (*.jpg *.jpeg *.png *.bmp *.webp)",
        )
        if not files:
            return

        self.last_photo_source_dir = str(
            Path(files[0]).resolve().parent
        )

        try:
            storage = self.photo_storage_dir()
        except OSError as error:
            QMessageBox.critical(
                self,
                "사진 폴더 생성 실패",
                f"사진 저장폴더를 만들 수 없습니다.\n\n{error}",
            )
            return

        target_row = int(slot["점검대상행"])
        target = self.target_row_data(target_row)
        added = 0

        for original_path_text in files:
            original_path = Path(original_path_text)
            if not original_path.exists():
                continue

            extension = original_path.suffix.lower() or ".jpg"
            stored_name = f"{uuid.uuid4().hex}{extension}"
            stored_path = storage / stored_name

            try:
                shutil.copy2(original_path, stored_path)
            except OSError as error:
                QMessageBox.warning(
                    self,
                    "사진 복사 실패",
                    f"{original_path.name} 파일을 복사하지 못했습니다.\n\n{error}",
                )
                continue

            self.photo_records.append(
                {
                    "사진ID": uuid.uuid4().hex,
                    "장비키": slot["장비키"],
                    "점검대상행": target_row,
                    "설비종류": target.get("설비종류", ""),
                    "점검번호": target.get("점검번호", ""),
                    "관리번호": target.get("관리번호", ""),
                    "장비표시": slot["장비표시"],
                    "점검항목": slot["점검항목"],
                    "사진구분": slot["사진구분"],
                    "촬영목록항목": slot["촬영항목"],
                    "원본파일명": original_path.name,
                    "저장경로": str(stored_path),
                    "설명": slot["촬영항목"],
                }
            )
            added += 1

        self.refresh_photo_table()
        self.refresh_photo_slot_table()
        self.refresh_shot_checklist()

        if added:
            self.status_label.setText(
                f"{slot['촬영항목']} 사진 {added}장을 등록했습니다."
            )

    def preview_photo_slot(self, row):
        item = self.photo_slot_table.item(row, 0)
        if item is None:
            return

        slot = item.data(Qt.UserRole)
        records = self.photo_records_for_slot(slot)
        if not records:
            return

        record = records[0]
        photo_id = record.get("사진ID")
        for table_row, existing in enumerate(self.photo_records):
            if existing.get("사진ID") == photo_id:
                self.photo_table.selectRow(table_row)
                self.on_photo_row_selected()
                break

    def build_shot_checklist_text(self):
        self.save_current_inspection_detail()
        lines = [
            "기계설비 성능점검 현장 촬영목록",
            "=" * 60,
            f"현장명: {self.site_name.text().strip()}",
            (
                "점검기간: "
                f"{self.inspection_start.date().toString('yyyy-MM-dd')} "
                f"~ {self.inspection_end.date().toString('yyyy-MM-dd')}"
            ),
            "",
        ]

        records = self.collect_photo_data()
        total_required = 0
        completed = 0

        for row in range(self.target_table.rowCount()):
            target = self.target_row_data(row)
            equipment_name = target.get("설비종류", "")
            inspection_number = target.get("점검번호", "")
            management_number = target.get("관리번호", "")
            equipment_key = self.target_key_from_row(row)

            lines.append(
                f"[{equipment_name} / 점검 {inspection_number}"
                f" / {management_number or '관리번호 미지정'}]"
            )

            requirements = list(
                self._photo_requirements_by_equipment.get(
                    equipment_name,
                    self._photo_base_requirements,
                )
            )

            for item in self._photo_inspection_db.get(equipment_name, []):
                if self.is_measurement_item(item):
                    measurement_label = (
                        f"측정사진: {item.get('name', '')}"
                    )
                    if measurement_label not in requirements:
                        requirements.append(measurement_label)

            saved_results = self.inspection_results.get(
                equipment_key,
                [],
            )

            if any(
                item.get("판정") == "조치필요"
                for item in saved_results
            ):
                requirements.append("결함사진")

            for requirement in requirements:
                total_required += 1

                if requirement.startswith("측정사진:"):
                    item_name = requirement.split(":", 1)[1].strip()
                    has_photo = any(
                        record.get("장비키") == equipment_key
                        and record.get("사진구분") == "측정사진"
                        and item_name in record.get("점검항목", "")
                        for record in records
                    )
                else:
                    has_photo = any(
                        record.get("장비키") == equipment_key
                        and record.get("사진구분") == requirement
                        for record in records
                    )

                if has_photo:
                    completed += 1

                lines.append(
                    f"  {'[완료]' if has_photo else '[미촬영]'} "
                    f"{requirement}"
                )

            lines.append("")

        lines.extend(
            [
                "-" * 60,
                (
                    f"필수 촬영항목 {total_required}건 | "
                    f"완료 {completed}건 | "
                    f"미촬영 {total_required - completed}건"
                ),
                "",
                "※ 측정사진은 계측기 표시값과 측정 대상 설비가 함께 확인되도록 촬영",
                "※ X 불합격 판정 시 이상부위가 식별되는 결함사진 촬영",
            ]
        )

        return "\n".join(lines)

    def refresh_shot_checklist(self):
        text = self.build_shot_checklist_text()
        self.shot_checklist_preview.setPlainText(text)
        self.status_label.setText(
            "현장 촬영목록을 새로고침했습니다."
        )

    def save_shot_checklist(self):
        text = self.build_shot_checklist_text()
        site_name = self.safe_filename(
            self.site_name.text().strip() or "현장미지정"
        )
        default_path = (
            Path.cwd()
            / f"{site_name}_성능점검_촬영목록.txt"
        )

        file_name, _ = QFileDialog.getSaveFileName(
            self,
            "촬영목록 저장",
            str(default_path),
            "텍스트 파일 (*.txt)",
        )

        if not file_name:
            return

        Path(file_name).write_text(
            text,
            encoding="utf-8-sig",
        )
        self.shot_checklist_preview.setPlainText(text)
        self.status_label.setText(
            f"촬영목록을 저장했습니다: {file_name}"
        )

    def photo_storage_dir(self):
        site_name = self.safe_filename(
            self.site_name.text().strip() or "현장미지정"
        )

        if self.current_file:
            project_base = Path(self.current_file).resolve().parent
        else:
            project_base = Path.cwd()

        folder = project_base / "성능점검사진" / site_name
        folder.mkdir(parents=True, exist_ok=True)
        return folder.resolve()

    def add_photos(self):
        target_row = self.photo_equipment_combo.currentData()

        if target_row is None:
            QMessageBox.warning(
                self,
                "점검대상 확인",
                "사진을 연결할 점검대상 장비를 선택하십시오.",
            )
            return

        try:
            target_row = int(target_row)
        except (TypeError, ValueError):
            QMessageBox.warning(
                self,
                "점검대상 오류",
                "점검대상 장비 연결정보가 올바르지 않습니다.",
            )
            return

        if target_row < 0 or target_row >= self.target_table.rowCount():
            QMessageBox.warning(
                self,
                "점검대상 오류",
                "점검대상 장비를 다시 새로고침하십시오.",
            )
            return

        initial_folder = self.last_photo_source_dir

        if not Path(initial_folder).exists():
            initial_folder = str(Path.home())

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "점검사진 선택",
            initial_folder,
            "이미지 파일 (*.jpg *.jpeg *.png *.bmp *.webp)",
        )

        if not files:
            return

        self.last_photo_source_dir = str(
            Path(files[0]).resolve().parent
        )

        target = self.target_row_data(target_row)
        equipment_key = self.target_key_from_row(target_row)
        equipment_label = self.photo_equipment_combo.currentText()
        inspection_item = self.photo_item_combo.currentText()
        photo_type = self.photo_type_combo.currentText()

        try:
            storage = self.photo_storage_dir()
        except OSError as error:
            QMessageBox.critical(
                self,
                "사진 폴더 생성 실패",
                f"사진 저장폴더를 만들 수 없습니다.\n\n{error}",
            )
            return

        added = 0

        for original_path_text in files:
            original_path = Path(original_path_text)

            if not original_path.exists():
                continue

            extension = original_path.suffix.lower() or ".jpg"
            stored_name = f"{uuid.uuid4().hex}{extension}"
            stored_path = storage / stored_name

            try:
                shutil.copy2(original_path, stored_path)
            except OSError as error:
                QMessageBox.warning(
                    self,
                    "사진 복사 실패",
                    f"{original_path.name} 파일을 복사하지 못했습니다.\n\n{error}",
                )
                continue

            self.photo_records.append(
                {
                    "사진ID": uuid.uuid4().hex,
                    "장비키": equipment_key,
                    "점검대상행": target_row,
                    "설비종류": target.get("설비종류", ""),
                    "점검번호": target.get("점검번호", ""),
                    "관리번호": target.get("관리번호", ""),
                    "장비표시": equipment_label,
                    "점검항목": inspection_item,
                    "사진구분": photo_type,
                    "원본파일명": original_path.name,
                    "저장경로": str(stored_path),
                    "설명": "",
                }
            )
            added += 1

        self.refresh_photo_table()
        if hasattr(self, "photo_slot_table"):
            self.refresh_photo_slot_table()
        if hasattr(self, "shot_checklist_preview"):
            self.refresh_shot_checklist()

        if added:
            self.status_label.setText(
                f"{equipment_label}에 점검사진 {added}장을 등록했습니다."
            )

    def refresh_photo_table(self):
        if not hasattr(self, "photo_table"):
            return

        self.photo_table.setRowCount(len(self.photo_records))

        for row, record in enumerate(self.photo_records):
            values = [
                record.get("장비표시", ""),
                record.get("점검항목", ""),
                record.get("사진구분", ""),
                record.get("원본파일명", ""),
                record.get("설명", ""),
                record.get("저장경로", ""),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.photo_table.setItem(row, column, item)

            self.photo_table.item(row, 0).setData(
                Qt.UserRole, record.get("사진ID")
            )

        self.photo_summary.setText(
            f"등록 사진 {len(self.photo_records)}장"
        )

        if not self.photo_records:
            self.current_photo_id = None
            self.photo_preview.clear()
            self.photo_preview.setText("사진을 선택하십시오.")
            self.photo_caption_edit.clear()

    def on_photo_row_selected(self):
        row = self.photo_table.currentRow()

        if row < 0 or row >= len(self.photo_records):
            return

        record = self.photo_records[row]
        self.current_photo_id = record.get("사진ID")
        self.photo_caption_edit.setPlainText(
            record.get("설명", "")
        )

        path = Path(record.get("저장경로", ""))

        if not path.exists():
            self.photo_preview.clear()
            self.photo_preview.setText(
                f"사진 파일을 찾을 수 없습니다.\n{path}"
            )
            return

        pixmap = QPixmap(str(path))

        if pixmap.isNull():
            self.photo_preview.clear()
            self.photo_preview.setText(
                "미리보기를 불러올 수 없습니다."
            )
            return

        scaled = pixmap.scaled(
            self.photo_preview.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.photo_preview.setPixmap(scaled)

    def save_photo_caption(self):
        if not self.current_photo_id:
            QMessageBox.warning(
                self,
                "사진 선택",
                "설명을 저장할 사진을 선택하십시오.",
            )
            return

        caption = self.photo_caption_edit.toPlainText().strip()

        selected_row = -1

        for index, record in enumerate(self.photo_records):
            if record.get("사진ID") == self.current_photo_id:
                record["설명"] = caption
                selected_row = index
                break

        self.refresh_photo_table()

        if selected_row >= 0:
            self.photo_table.selectRow(selected_row)

        self.status_label.setText("사진 설명을 저장했습니다.")

    def remove_selected_photo(self):
        row = self.photo_table.currentRow()

        if row < 0 or row >= len(self.photo_records):
            QMessageBox.warning(
                self,
                "사진 선택",
                "삭제할 사진을 선택하십시오.",
            )
            return

        record = self.photo_records[row]

        answer = QMessageBox.question(
            self,
            "사진 삭제",
            f"{record.get('원본파일명', '')} 사진을 삭제하시겠습니까?",
        )

        if answer != QMessageBox.Yes:
            return

        stored_path = Path(record.get("저장경로", ""))

        try:
            if stored_path.exists():
                stored_path.unlink()
        except OSError as error:
            QMessageBox.warning(
                self,
                "파일 삭제 안내",
                f"사진 목록에서는 삭제했지만 파일 삭제에 실패했습니다.\n\n{error}",
            )

        del self.photo_records[row]
        self.current_photo_id = None
        self.refresh_photo_table()
        if hasattr(self, "photo_slot_table"):
            self.refresh_photo_slot_table()
        if hasattr(self, "shot_checklist_preview"):
            self.refresh_shot_checklist()

    def open_photo_storage_folder(self):
        try:
            folder = self.photo_storage_dir()
        except OSError as error:
            QMessageBox.critical(
                self,
                "사진 저장폴더 오류",
                f"사진 저장폴더를 만들 수 없습니다.\n\n{error}",
            )
            return

        try:
            import subprocess

            subprocess.Popen(
                ["explorer", str(folder)],
                shell=False,
            )
            self.status_label.setText(
                f"사진 저장폴더를 열었습니다: {folder}"
            )
        except OSError as error:
            QMessageBox.information(
                self,
                "사진 저장폴더",
                f"아래 경로를 파일 탐색기에 붙여 넣으십시오.\n\n{folder}\n\n{error}",
            )

    def collect_photo_data(self):
        clean_records = []

        for record in self.photo_records:
            clean = {}
            for key, value in record.items():
                if isinstance(
                    value,
                    (str, int, float, bool, type(None)),
                ):
                    clean[str(key)] = value
                else:
                    clean[str(key)] = str(value)

            clean_records.append(clean)

        return clean_records


    def load_photo_data(self, records):
        self.photo_records = records if isinstance(records, list) else []
        self.current_photo_id = None

        if hasattr(self, "photo_table"):
            self.refresh_photo_table()
        if hasattr(self, "photo_slot_table"):
            self.refresh_photo_slot_table()
