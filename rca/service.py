from .rules import (
    get_equipment_cause_rule,
    get_inspection_cause_rule,
)


class RcaServiceMixin:
    def cause_rule_for_equipment(self, equipment_name):
        return get_equipment_cause_rule(equipment_name)

    def cause_rule_for_inspection(self, equipment_name, result):
        return get_inspection_cause_rule(
            equipment_name,
            result,
        )

    def migrate_special_cause_analysis(self):
        """
        v3.14.1 이전에 장비 원인DB가 잘못 적용된 문서성 불합격을 교정한다.
        사용자가 최종원인을 직접 확정한 경우에는 덮어쓰지 않는다.
        """
        if not isinstance(self.cause_analysis, list):
            return

        # 현재 점검결과를 빠르게 조회
        lookup = {}
        for target_row in range(self.target_table.rowCount()):
            key = self.target_key_from_row(target_row)
            target = self.target_row_data(target_row)
            for result in self.inspection_results.get(key, []):
                lookup[
                    (key, str(result.get("번호", "")))
                ] = (
                    target.get("설비종류", ""),
                    result,
                )
        for row in self.cause_analysis:
            key = row.get("장비키", "")
            item_no = str(row.get("점검번호", ""))
            found = lookup.get((key, item_no))
            if not found:
                continue

            equipment_name, result = found
            rule, is_special = self.cause_rule_for_inspection(
                equipment_name,
                result,
            )
            if not is_special:
                continue

            # 최종원인이 확정된 자료는 사용자 판단을 존중
            if str(row.get("최종원인", "")).strip():
                continue

            equipment_rule = self.cause_rule_for_equipment(
                equipment_name
            )

            old_improvement = str(
                row.get("개선방안", "")
            ).strip()
            old_candidates = str(
                row.get("원인후보", "")
            ).strip()

            looks_like_old_generic = (
                not old_improvement
                or old_improvement == equipment_rule.get("개선", "")
                or any(
                    candidate in old_candidates
                    for candidate in equipment_rule.get("원인후보", [])[:2]
                )
            )

            if looks_like_old_generic:
                row["이상현상"] = rule["증상"]
                row["원인후보"] = "\n".join(
                    f"• {value}"
                    for value in rule["원인후보"]
                )
                row["원인확인방법"] = "\n".join(
                    f"• {value}"
                    for value in rule["확인방법"]
                )
                row["영향"] = rule["영향"]
                row["개선방안"] = rule["개선"]
                row["우선순위"] = rule.get(
                    "우선순위",
                    "B-단기",
                )
