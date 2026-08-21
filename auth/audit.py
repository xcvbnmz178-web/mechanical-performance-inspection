import json
from datetime import datetime


class AuditStore:
    def __init__(self, root):
        self.root = root
        self.path = root / "audit_log.jsonl"

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
        """
        모바일/API 연동을 고려한 단순 JSONL 감사로그.
        비밀번호·해시·토큰은 절대 기록하지 않는다.
        """
        try:
            record = {
                "timestamp": datetime.now().astimezone().isoformat(
                    timespec="seconds"
                ),
                "user_id": str(
                    (user or {}).get("id", "")
                ),
                "display_name": str(
                    (user or {}).get("display_name", "")
                ),
                "role": str(
                    (user or {}).get("role", "")
                ),
                "action": str(action or ""),
                "site": str(site or ""),
                "target": str(target or ""),
                "field": str(field or ""),
                "before": str(before or ""),
                "after": str(after or ""),
                "detail": str(detail or ""),
            }

            with self.path.open(
                "a",
                encoding="utf-8",
            ) as file:
                file.write(
                    json.dumps(
                        record,
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                file.flush()
        except Exception as error:
            # 작업기록 실패 때문에 본 프로그램 작업은 중단하지 않되,
            # 원인 확인을 위해 별도 오류 로그를 남긴다.
            try:
                error_path = self.root / "audit_error.log"
                with error_path.open(
                    "a",
                    encoding="utf-8",
                ) as error_file:
                    error_file.write(
                        f"{datetime.now().isoformat(timespec='seconds')} "
                        f"{type(error).__name__}: {error}\n"
                    )
            except Exception:
                pass

    def load_audit(self):
        if not self.path.exists():
            return []

        records = []

        try:
            text = self.path.read_text(
                encoding="utf-8"
            )
        except Exception:
            return []

        # v3.16 초기판 호환:
        # 실제 줄바꿈 대신 문자 "\\n"이 들어간 로그도 복구해서 읽는다.
        chunks = []
        for physical_line in text.splitlines():
            if "\\n" in physical_line:
                chunks.extend(
                    part
                    for part in physical_line.split("\\n")
                    if part.strip()
                )
            elif physical_line.strip():
                chunks.append(physical_line)

        for line in chunks:
            line = line.strip()
            if not line:
                continue

            try:
                data = json.loads(line)
            except Exception:
                continue

            if isinstance(data, dict):
                records.append(data)

        return records
