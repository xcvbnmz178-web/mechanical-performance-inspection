import csv
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class FirstAdminDialog(QDialog):
    def __init__(self, auth_manager, parent=None):
        super().__init__(parent)
        self.auth = auth_manager
        self.created = False

        self.setWindowTitle("최초 관리자 계정 생성")
        self.setModal(True)
        self.resize(430, 280)

        layout = QVBoxLayout(self)

        notice = QLabel(
            "최초 실행입니다. 프로그램을 관리할 관리자 계정을 생성하십시오.\n"
            "비밀번호는 원문으로 저장하지 않고 PBKDF2 해시로 저장됩니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding:10px; background:#eef6ff; border:1px solid #9ec5e5;"
        )
        layout.addWidget(notice)

        form = QFormLayout()

        self.user_id = QLineEdit()
        self.user_id.setPlaceholderText("예: admin")

        self.display_name = QLineEdit()
        self.display_name.setPlaceholderText("예: 관리자")

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        self.password_confirm = QLineEdit()
        self.password_confirm.setEchoMode(QLineEdit.Password)

        form.addRow("관리자 아이디", self.user_id)
        form.addRow("사용자명", self.display_name)
        form.addRow("비밀번호", self.password)
        form.addRow("비밀번호 확인", self.password_confirm)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(
            QDialogButtonBox.Ok
        ).setText("관리자 생성")
        buttons.accepted.connect(self.create_admin)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def create_admin(self):
        if self.password.text() != self.password_confirm.text():
            QMessageBox.warning(
                self,
                "확인",
                "비밀번호가 일치하지 않습니다.",
            )
            return

        try:
            self.auth.create_user(
                self.user_id.text(),
                self.password.text(),
                self.display_name.text(),
                role="admin",
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "관리자 생성 실패",
                str(error),
            )
            return

        created_user = self.auth.authenticate(
            self.user_id.text(),
            self.password.text(),
        )
        self.auth.write_audit(
            created_user,
            "최초 관리자 생성",
            target=self.user_id.text().strip(),
        )

        self.created = True
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, auth_manager, parent=None):
        super().__init__(parent)
        self.auth = auth_manager
        self.user = None

        self.setWindowTitle("기계설비 성능점검 시스템 로그인")
        self.setModal(True)
        self.resize(430, 300)

        layout = QVBoxLayout(self)

        title = QLabel("기계설비 성능점검 시스템")
        title.setStyleSheet(
            "font-size:22px; font-weight:bold; padding:10px;"
        )
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(
            "현장 성능점검 · 원인분석 · 에너지 분석"
        )
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            "color:#4b5563; padding-bottom:12px;"
        )
        layout.addWidget(subtitle)

        form = QFormLayout()

        self.user_id = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)

        form.addRow("아이디", self.user_id)
        form.addRow("비밀번호", self.password)
        layout.addLayout(form)

        option_row = QHBoxLayout()
        self.remember_id = QCheckBox("아이디 저장")
        self.auto_login = QCheckBox("자동 로그인")
        option_row.addWidget(self.remember_id)
        option_row.addWidget(self.auto_login)
        option_row.addStretch()
        layout.addLayout(option_row)

        saved_id = self.auth.settings.value(
            "saved_user_id",
            "",
            type=str,
        )
        remember = self.auth.settings.value(
            "remember_id",
            False,
            type=bool,
        )
        auto_login = self.auth.settings.value(
            "auto_login",
            False,
            type=bool,
        )

        self.remember_id.setChecked(remember)
        self.auto_login.setChecked(auto_login)

        if remember and saved_id:
            self.user_id.setText(saved_id)
            self.password.setFocus()
        else:
            self.user_id.setFocus()

        login_button = QPushButton("로그인")
        login_button.setMinimumHeight(42)
        login_button.clicked.connect(self.try_login)
        layout.addWidget(login_button)

        self.password.returnPressed.connect(self.try_login)

    def try_login(self):
        user = self.auth.authenticate(
            self.user_id.text(),
            self.password.text(),
        )

        if not user:
            QMessageBox.warning(
                self,
                "로그인 실패",
                "아이디 또는 비밀번호가 올바르지 않습니다.",
            )
            self.password.selectAll()
            self.password.setFocus()
            return

        self.user = user

        remember = self.remember_id.isChecked()
        self.auth.settings.setValue(
            "remember_id",
            remember,
        )
        self.auth.settings.setValue(
            "saved_user_id",
            self.user_id.text().strip()
            if remember else "",
        )

        # 로컬 자동 로그인은 비밀번호를 저장하지 않는다.
        # 로그인 성공 계정 ID만 기억하고, OS 사용자 계정 내부 설정을 이용한다.
        # 실제 무비밀번호 자동 로그인은 보안상 지원하지 않고
        # 추후 서버 토큰 방식으로 전환 예정.
        self.auth.settings.setValue(
            "auto_login",
            self.auto_login.isChecked(),
        )
        self.auth.settings.sync()

        self.auth.write_audit(
            self.user,
            "로그인",
        )

        self.accept()



class AuditLogDialog(QDialog):
    def __init__(self, auth_manager, current_user, parent=None):
        super().__init__(parent)
        self.auth = auth_manager
        self.current_user = current_user

        self.setWindowTitle("사용자별 작업기록")
        self.resize(1180, 620)

        layout = QVBoxLayout(self)

        role_text = (
            "관리자: 전체 사용자 기록"
            if current_user.get("role") == "admin"
            else "일반사용자: 본인 작업기록"
        )
        notice = QLabel(
            f"{role_text}을 표시합니다. "
            "점검 측정값·판정·기술적소견 변경, 프로젝트 저장·열기 등의 이력을 기록합니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding:8px; background:#eef6ff; border:1px solid #9ec5e5;"
        )
        layout.addWidget(notice)

        path_label = QLabel(
            f"기록파일: {self.auth.audit_path}"
        )
        path_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        path_label.setStyleSheet(
            "color:#555; padding:4px;"
        )
        layout.addWidget(path_label)

        filter_row = QHBoxLayout()
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText(
            "현장명, 장비, 작업내용 검색"
        )
        refresh_button = QPushButton("새로고침")
        refresh_button.clicked.connect(self.refresh_table)
        self.keyword.textChanged.connect(self.refresh_table)

        filter_row.addWidget(QLabel("검색"))
        filter_row.addWidget(self.keyword)
        filter_row.addWidget(refresh_button)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "일시",
                "사용자",
                "작업",
                "현장",
                "대상",
                "항목",
                "변경 전",
                "변경 후",
                "상세",
            ]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        for col in [0, 1, 2]:
            header.setSectionResizeMode(
                col,
                QHeaderView.ResizeToContents,
            )
        self.table.setWordWrap(True)
        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        export_button = QPushButton("CSV 내보내기")
        export_button.clicked.connect(self.export_csv)
        close_button = QPushButton("닫기")
        close_button.clicked.connect(self.accept)

        buttons.addWidget(export_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.refresh_table()

    def visible_records(self):
        records = self.auth.load_audit()

        if self.current_user.get("role") != "admin":
            user_id = self.current_user.get("id", "")
            records = [
                record
                for record in records
                if record.get("user_id") == user_id
            ]

        keyword = self.keyword.text().strip().lower()
        if keyword:
            filtered = []
            for record in records:
                haystack = " ".join(
                    str(record.get(key, ""))
                    for key in [
                        "display_name",
                        "user_id",
                        "action",
                        "site",
                        "target",
                        "field",
                        "before",
                        "after",
                        "detail",
                    ]
                ).lower()
                if keyword in haystack:
                    filtered.append(record)
            records = filtered

        return list(reversed(records))

    def refresh_table(self):
        records = self.visible_records()
        self.table.setRowCount(len(records))

        for row, record in enumerate(records):
            timestamp = str(
                record.get("timestamp", "")
            ).replace("T", " ")
            if "+" in timestamp:
                timestamp = timestamp.split("+", 1)[0]

            user = (
                record.get("display_name")
                or record.get("user_id")
                or ""
            )

            values = [
                timestamp,
                user,
                record.get("action", ""),
                record.get("site", ""),
                record.get("target", ""),
                record.get("field", ""),
                record.get("before", ""),
                record.get("after", ""),
                record.get("detail", ""),
            ]

            for col, value in enumerate(values):
                self.table.setItem(
                    row,
                    col,
                    QTableWidgetItem(str(value)),
                )

        self.table.resizeRowsToContents()

    def export_csv(self):
        records = self.visible_records()
        if not records:
            QMessageBox.information(
                self,
                "작업기록",
                "내보낼 작업기록이 없습니다.",
            )
            return

        default_name = (
            "전체_작업기록.csv"
            if self.current_user.get("role") == "admin"
            else f"{self.current_user.get('id','user')}_작업기록.csv"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "작업기록 CSV 저장",
            str(Path.home() / default_name),
            "CSV 파일 (*.csv)",
        )
        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        with open(
            file_path,
            "w",
            newline="",
            encoding="utf-8-sig",
        ) as file:
            writer = csv.writer(file)
            writer.writerow(
                [
                    "일시",
                    "아이디",
                    "사용자명",
                    "권한",
                    "작업",
                    "현장",
                    "대상",
                    "항목",
                    "변경 전",
                    "변경 후",
                    "상세",
                ]
            )
            for record in reversed(records):
                writer.writerow(
                    [
                        record.get("timestamp", ""),
                        record.get("user_id", ""),
                        record.get("display_name", ""),
                        record.get("role", ""),
                        record.get("action", ""),
                        record.get("site", ""),
                        record.get("target", ""),
                        record.get("field", ""),
                        record.get("before", ""),
                        record.get("after", ""),
                        record.get("detail", ""),
                    ]
                )

        QMessageBox.information(
            self,
            "CSV 저장 완료",
            f"작업기록을 저장했습니다.\\n\\n{file_path}",
        )


class UserManagementDialog(QDialog):
    def __init__(self, auth_manager, current_user, parent=None):
        super().__init__(parent)
        self.auth = auth_manager
        self.current_user = current_user

        self.setWindowTitle("사용자 관리")
        self.resize(720, 440)

        layout = QVBoxLayout(self)

        notice = QLabel(
            "관리자 전용 기능입니다. 사용자 추가·삭제 및 비밀번호 초기화를 할 수 있습니다."
        )
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "padding:8px; background:#fff7d6; border:1px solid #e6c65c;"
        )
        layout.addWidget(notice)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["아이디", "사용자명", "권한", "사용상태"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        add_button = QPushButton("사용자 추가")
        reset_button = QPushButton("비밀번호 변경")
        delete_button = QPushButton("사용자 삭제")
        close_button = QPushButton("닫기")

        add_button.clicked.connect(self.add_user)
        reset_button.clicked.connect(self.reset_password)
        delete_button.clicked.connect(self.delete_user)
        close_button.clicked.connect(self.accept)

        buttons.addWidget(add_button)
        buttons.addWidget(reset_button)
        buttons.addWidget(delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.refresh_table()

    def refresh_table(self):
        users = self.auth.load_users()
        self.table.setRowCount(len(users))

        for row, user in enumerate(users):
            values = [
                user.get("id", ""),
                user.get("display_name", ""),
                "관리자" if user.get("role") == "admin" else "일반사용자",
                "사용" if user.get("enabled", True) else "중지",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(
                    Qt.ItemIsEnabled | Qt.ItemIsSelectable
                )
                self.table.setItem(row, col, item)

    def selected_user_id(self):
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 0)
        return item.text().strip() if item else ""

    def add_user(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("사용자 추가")
        form_layout = QVBoxLayout(dialog)
        form = QFormLayout()

        user_id = QLineEdit()
        display_name = QLineEdit()
        password = QLineEdit()
        password.setEchoMode(QLineEdit.Password)
        role = QComboBox()
        role.addItem("일반사용자", "user")
        role.addItem("관리자", "admin")

        form.addRow("아이디", user_id)
        form.addRow("사용자명", display_name)
        form.addRow("초기 비밀번호", password)
        form.addRow("권한", role)
        form_layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form_layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        try:
            self.auth.create_user(
                user_id.text(),
                password.text(),
                display_name.text(),
                role=role.currentData(),
            )
            self.auth.write_audit(
                self.current_user,
                "사용자 추가",
                target=user_id.text().strip(),
                after=(
                    "관리자"
                    if role.currentData() == "admin"
                    else "일반사용자"
                ),
                detail=display_name.text().strip(),
            )
            self.refresh_table()
        except Exception as error:
            QMessageBox.warning(
                self,
                "사용자 추가 실패",
                str(error),
            )

    def reset_password(self):
        user_id = self.selected_user_id()
        if not user_id:
            QMessageBox.information(
                self,
                "사용자 선택",
                "비밀번호를 변경할 사용자를 선택하십시오.",
            )
            return

        dialog = QDialog(self)
        dialog.setWindowTitle("비밀번호 변경")
        layout = QVBoxLayout(dialog)
        form = QFormLayout()

        password = QLineEdit()
        password.setEchoMode(QLineEdit.Password)
        confirm = QLineEdit()
        confirm.setEchoMode(QLineEdit.Password)

        form.addRow("새 비밀번호", password)
        form.addRow("비밀번호 확인", confirm)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.Accepted:
            return

        if password.text() != confirm.text():
            QMessageBox.warning(
                self,
                "확인",
                "비밀번호가 일치하지 않습니다.",
            )
            return

        try:
            self.auth.set_password(
                user_id,
                password.text(),
            )
            self.auth.write_audit(
                self.current_user,
                "비밀번호 변경",
                target=user_id,
                detail="비밀번호 내용은 기록하지 않음",
            )
            QMessageBox.information(
                self,
                "완료",
                "비밀번호를 변경했습니다.",
            )
        except Exception as error:
            QMessageBox.warning(
                self,
                "변경 실패",
                str(error),
            )

    def delete_user(self):
        user_id = self.selected_user_id()
        if not user_id:
            QMessageBox.information(
                self,
                "사용자 선택",
                "삭제할 사용자를 선택하십시오.",
            )
            return

        if user_id == self.current_user.get("id"):
            QMessageBox.warning(
                self,
                "삭제 불가",
                "현재 로그인한 계정은 삭제할 수 없습니다.",
            )
            return

        answer = QMessageBox.question(
            self,
            "사용자 삭제",
            f"{user_id} 계정을 삭제하시겠습니까?",
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.auth.delete_user(user_id)
            self.auth.write_audit(
                self.current_user,
                "사용자 삭제",
                target=user_id,
            )
            self.refresh_table()
        except Exception as error:
            QMessageBox.warning(
                self,
                "삭제 실패",
                str(error),
            )
