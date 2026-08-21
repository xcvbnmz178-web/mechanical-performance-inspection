import re


class ComparisonServiceMixin:

    @staticmethod
    def previous_numeric_value(value):
        if value is None:
            return None
        match = re.search(
            r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)",
            str(value).replace(",", ""),
        )
        if not match:
            return None
        try:
            return float(match.group(0))
        except ValueError:
            return None

    def previous_project_inspection_map(self, project):
        """
        구버전 key가 행번호를 포함하므로 직접 key를 비교하지 않고
        설비종류 + 관리번호 + 점검항목 번호로 안정적인 비교키를 만든다.
        """
        register = project.get("장비대장", [])
        targets = project.get("점검대상선정", [])
        results = project.get("설비별점검결과", {})

        output = {}

        for row, target in enumerate(targets):
            equipment = target.get("설비종류", "")
            inspection_number = str(
                target.get("점검번호", "")
            )
            register_row = target.get("장비대장행", -1)

            management_number = ""
            try:
                register_index = int(register_row)
                if 0 <= register_index < len(register):
                    management_number = register[
                        register_index
                    ].get("관리번호", "")
            except (TypeError, ValueError):
                register_index = -1

            old_key = (
                f"{equipment}|{inspection_number}|"
                f"{register_index}|{row}"
            )

            rows = results.get(old_key, [])

            # 일부 구버전에서 key 형식이 달라졌을 수 있어 보조 검색
            if not rows:
                prefix = (
                    f"{equipment}|{inspection_number}|"
                    f"{register_index}|"
                )
                for key, candidate in results.items():
                    if str(key).startswith(prefix):
                        rows = candidate
                        break

            for item in rows:
                item_no = str(item.get("번호", ""))
                signature = (
                    equipment,
                    management_number,
                    item_no,
                )
                output[signature] = {
                    **item,
                    "설비종류": equipment,
                    "관리번호": management_number,
                    "점검번호": inspection_number,
                }

        return output

    def current_inspection_compare_map(self):
        self.save_current_inspection_detail()
        output = {}

        for target_row in range(self.target_table.rowCount()):
            target = self.target_row_data(target_row)
            key = self.target_key_from_row(target_row)

            for item in self.inspection_results.get(key, []):
                signature = (
                    target.get("설비종류", ""),
                    target.get("관리번호", ""),
                    str(item.get("번호", "")),
                )
                output[signature] = {
                    **item,
                    "설비종류": target.get("설비종류", ""),
                    "관리번호": target.get("관리번호", ""),
                    "점검번호": target.get("점검번호", ""),
                }

        return output

    @staticmethod
    def previous_latest_energy(project):
        rows = (
            project.get("에너지분석", {})
            .get("에너지사용량", [])
        )
        by_year = {}

        for row in rows:
            year = str(row.get("연도", "")).strip()
            energy_type = str(
                row.get("종류", "")
            ).strip()
            try:
                usage = float(
                    str(row.get("총 사용량", ""))
                    .replace(",", "")
                    .strip()
                    or 0
                )
            except ValueError:
                usage = 0.0

            if year and energy_type:
                by_year.setdefault(year, {})[
                    energy_type
                ] = usage

        if not by_year:
            return "", {}

        year = sorted(by_year.keys())[-1]
        return year, by_year[year]
    def build_previous_comparison_rows(self):

        previous_map = self.previous_project_inspection_map(
            self.previous_project_data
        )
        current_map = self.current_inspection_compare_map()

        rows = []
        issue_count = 0

        all_keys = sorted(
            set(previous_map.keys()) | set(current_map.keys())
        )

        for signature in all_keys:
            previous = previous_map.get(signature)
            current = current_map.get(signature)

            if not previous or not current:
                continue

            equipment, management_number, _ = signature
            item_name = (
                current.get("점검내용")
                or previous.get("점검내용")
                or ""
            )

            previous_result = previous.get("판정", "")
            current_result = current.get("판정", "")

            if previous_result != current_result:
                opinion = ""
                judge = "변화"
                if (
                    self.is_final_pass(previous_result)
                    and self.is_final_fail(current_result)
                ):
                    judge = "원인확인"
                    opinion = (
                        "전년도 적합에서 금년도 조치필요로 변경됨. "
                        "운전조건·노후화·정비이력 및 관련 계측값 확인 필요."
                    )
                    issue_count += 1

                rows.append(
                    {
                        "구분": "점검판정",
                        "대상": (
                            f"{equipment} / "
                            f"{management_number or '관리번호 미지정'}"
                        ),
                        "항목": item_name,
                        "전년": previous_result or "-",
                        "금년": current_result or "-",
                        "변화": f"{previous_result} → {current_result}",
                        "판정": judge,
                        "의견": opinion,
                    }
                )

            previous_value = self.previous_numeric_value(
                previous.get("측정확인값")
            )
            current_value = self.previous_numeric_value(
                current.get("측정확인값")
            )

            if (
                previous_value is not None
                and current_value is not None
                and previous_value != 0
            ):
                ratio = current_value / previous_value * 100.0
                change = (
                    (current_value - previous_value)
                    / previous_value
                    * 100.0
                )

                performance_metric = bool(
                    re.search(
                        r"COP|효율|유효도",
                        item_name,
                        re.IGNORECASE,
                    )
                )

                judge = "참고"
                opinion = ""

                if performance_metric and ratio < 90.0:
                    judge = "원인확인"
                    opinion = (
                        "주요 성능지표가 전년도 대비 90% 미만. "
                        "부하조건을 확인하고 동일 운전조건에서 재측정 후 "
                        "성능저하 원인분석 필요."
                    )
                    issue_count += 1

                if abs(change) >= 5 or performance_metric:
                    unit = current.get("단위", "") or previous.get(
                        "단위", ""
                    )
                    rows.append(
                        {
                            "구분": "측정값",
                            "대상": (
                                f"{equipment} / "
                                f"{management_number or '관리번호 미지정'}"
                            ),
                            "항목": item_name,
                            "전년": f"{previous_value:g} {unit}".strip(),
                            "금년": f"{current_value:g} {unit}".strip(),
                            "변화": f"{change:+.1f}%",
                            "판정": judge,
                            "의견": opinion,
                        }
                    )

        # 최근 에너지 사용량 비교
        prev_year, prev_energy = self.previous_latest_energy(
            self.previous_project_data
        )
        cur_year, cur_energy = self.current_latest_energy()

        for energy_type, unit in [
            ("가스", "N㎥"),
            ("전기", "kWh"),
        ]:
            pv = prev_energy.get(energy_type, 0)
            cv = cur_energy.get(energy_type, 0)

            if pv > 0 and cv > 0:
                change = (cv - pv) / pv * 100.0
                bad = change >= 5.0

                if bad:
                    issue_count += 1

                rows.append(
                    {
                        "구분": "에너지",
                        "대상": energy_type,
                        "항목": "최근년도 사용량",
                        "전년": f"{prev_year}년 {pv:,.0f} {unit}",
                        "금년": f"{cur_year}년 {cv:,.0f} {unit}",
                        "변화": f"{change:+.1f}%",
                        "판정": (
                            "증가원인확인"
                            if bad else "양호"
                        ),
                        "의견": (
                            "5% 이상 증가. 운전시간·부하·기상조건·설비효율 "
                            "변화를 확인하고 증가 원인을 분석할 필요가 있음."
                            if bad
                            else "현저한 증가 없음."
                        ),
                    }
                )


        return rows, issue_count


    def current_latest_energy(self):
        by_year = {}

        for row in range(self.energy_table.rowCount()):
            year = self.table_item_text(
                self.energy_table, row, 0
            )
            energy_type = self.table_item_text(
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

            if year and energy_type:
                by_year.setdefault(year, {})[
                    energy_type
                ] = usage

        if not by_year:
            return "", {}

        year = sorted(by_year.keys())[-1]
        return year, by_year[year]
