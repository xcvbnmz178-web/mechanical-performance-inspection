import base64
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

from PySide6.QtCore import QSettings

from .audit import AuditStore


APP_ORGANIZATION = "ChokwangEngineering"
APP_NAME = "MechanicalPerformanceInspection"


def app_data_dir():
    """
    인증/설정 데이터는 프로그램 파일과 분리한다.
    Windows에서는 LOCALAPPDATA를 우선 사용한다.
    추후 모바일/서버 연동 시 이 저장소를 API 인증으로 교체하기 쉽도록 분리.
    """
    base = os.environ.get("LOCALAPPDATA")
    if base:
        root = Path(base) / APP_ORGANIZATION / APP_NAME
    else:
        root = Path.home() / f".{APP_NAME}"
    root.mkdir(parents=True, exist_ok=True)
    return root


class AuthManager:
    ITERATIONS = 310_000

    def __init__(self):
        self.root = app_data_dir()
        self.users_path = self.root / "users.json"
        self.audit_store = AuditStore(self.root)
        self.audit_path = self.audit_store.path
        self.settings = QSettings(
            APP_ORGANIZATION,
            APP_NAME + "_Auth",
        )

    def write_audit(
        self,
        user,
        action,
        site="",
        target="",
        field="",
        before="",
        after="",
        detail="",
    ):
        return self.audit_store.write_audit(
            user,
            action,
            site=site,
            target=target,
            field=field,
            before=before,
            after=after,
            detail=detail,
        )

    def load_audit(self):
        return self.audit_store.load_audit()

    @staticmethod
    def _hash_password(password, salt=None):
        if salt is None:
            salt = secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            AuthManager.ITERATIONS,
        )
        return (
            base64.b64encode(salt).decode("ascii"),
            base64.b64encode(digest).decode("ascii"),
        )

    def load_users(self):
        if not self.users_path.exists():
            return []
        try:
            data = json.loads(
                self.users_path.read_text(encoding="utf-8")
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def save_users(self, users):
        self.users_path.write_text(
            json.dumps(
                users,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def has_users(self):
        return bool(self.load_users())

    def create_user(self, user_id, password, display_name, role="user"):
        user_id = str(user_id).strip()
        display_name = str(display_name).strip() or user_id

        if not user_id:
            raise ValueError("아이디를 입력하십시오.")
        if len(password) < 6:
            raise ValueError("비밀번호는 6자 이상으로 입력하십시오.")

        users = self.load_users()
        if any(
            user.get("id", "").lower() == user_id.lower()
            for user in users
        ):
            raise ValueError("이미 존재하는 아이디입니다.")

        salt, password_hash = self._hash_password(password)
        users.append(
            {
                "id": user_id,
                "display_name": display_name,
                "role": role,
                "salt": salt,
                "password_hash": password_hash,
                "enabled": True,
            }
        )
        self.save_users(users)

    def authenticate(self, user_id, password):
        for user in self.load_users():
            if (
                user.get("id", "").lower()
                != str(user_id).strip().lower()
            ):
                continue

            if not user.get("enabled", True):
                return None

            try:
                salt = base64.b64decode(
                    user.get("salt", "")
                )
                expected = base64.b64decode(
                    user.get("password_hash", "")
                )
            except Exception:
                return None

            _, actual_b64 = self._hash_password(
                password,
                salt=salt,
            )
            actual = base64.b64decode(actual_b64)

            if hmac.compare_digest(actual, expected):
                return dict(user)

        return None

    def set_password(self, user_id, new_password):
        if len(new_password) < 6:
            raise ValueError("비밀번호는 6자 이상으로 입력하십시오.")

        users = self.load_users()
        found = False

        for user in users:
            if user.get("id") == user_id:
                salt, password_hash = self._hash_password(
                    new_password
                )
                user["salt"] = salt
                user["password_hash"] = password_hash
                found = True
                break

        if not found:
            raise ValueError("사용자를 찾을 수 없습니다.")

        self.save_users(users)

    def delete_user(self, user_id):
        users = self.load_users()

        target = next(
            (u for u in users if u.get("id") == user_id),
            None,
        )
        if not target:
            return

        if target.get("role") == "admin":
            admins = [
                u for u in users
                if u.get("role") == "admin"
                and u.get("enabled", True)
            ]
            if len(admins) <= 1:
                raise ValueError(
                    "마지막 관리자 계정은 삭제할 수 없습니다."
                )

        users = [
            user for user in users
            if user.get("id") != user_id
        ]
        self.save_users(users)
