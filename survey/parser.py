import math
import re

from PySide6.QtCore import QDate


class SurveyParserMixin:
    @staticmethod
    def survey_first_number(text):
        match = re.search(
            r"(\d+(?:,\d{3})*(?:\.\d+)?)",
            str(text),
        )
        return (
            match.group(1).replace(",", "")
            if match
            else ""
        )

    @staticmethod
    def survey_normalize_lines(text):
        normalized = str(text)

        # HWP 표 셀·문단 구분 제어문자를 줄바꿈으로 전환
        normalized = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]+",
            "\n",
            normalized,
        )
        normalized = normalized.replace("\r", "\n")
        normalized = re.sub(r"\n{2,}", "\n", normalized)

        lines = []
        for line in normalized.split("\n"):
            line = re.sub(r"[\t|]+", " ", line)
            line = re.sub(r"\s+", " ", line).strip()
            if line:
                lines.append(line)

        return lines

    @staticmethod
    def survey_compact_text(text):
        return re.sub(
            r"[^0-9A-Za-z가-힣]",
            "",
            str(text),
        ).lower()

    @staticmethod
    def standard_survey_tokens(text):
        """조광설비 표준 대상조사표의 셀 순서를 보존한 토큰 목록."""
        normalized = str(text).replace("\r", "\n")
        normalized = re.sub(
            r"[\x00-\x08\x0b\x0c\x0e-\x1f]+",
            "\n",
            normalized,
        )

        tokens = []
        for value in normalized.split("\n"):
            value = re.sub(r"\s+", " ", value).strip()
            if value:
                tokens.append(value)

        return tokens

    @staticmethod
    def token_compact(value):
        return re.sub(
            r"[^0-9A-Za-z가-힣]",
            "",
            str(value),
        ).lower()

    @staticmethod
    def quantity_from_token(value):
        match = re.search(
            r"(\d+(?:,\d{3})*)\s*(대|식|개|개층)?",
            str(value),
        )
        if not match:
            return None

        number = int(match.group(1).replace(",", ""))
        unit = match.group(2) or ""
        return number, unit

    def standard_value_after_token(self, tokens, labels, max_offset=4):
        compact_labels = {
            self.token_compact(label)
            for label in labels
        }

        for index, token in enumerate(tokens):
            if self.token_compact(token) not in compact_labels:
                continue

            for next_index in range(
                index + 1,
                min(index + max_offset + 1, len(tokens)),
            ):
                value = tokens[next_index].strip()
                if value:
                    return value

        return ""

    def standard_equipment_definitions(self):
        """
        실제 제공된 대상조사표의 표기 순서.
        별도 설비명이 없는 1식 항목은 구분명 자체를 사용한다.
        """
        return [
            ("냉동기", ["냉동기"]),
            ("냉각탑", ["냉각탑"]),
            ("축열조", ["축열조"]),
            ("보일러", ["보일러"]),
            ("열교환기", ["열교환기"]),
            ("팽창탱크", ["팽창탱크"]),
            ("펌프(냉난방·급수)", ["펌프"]),
            ("신재생에너지(태양열·지열)", ["신재생에너지"]),
            ("패키지에어컨", ["패키지 에어콘", "패키지 에어컨"]),
            ("항온항습기", ["항온항습기"]),
            ("공기조화기", ["공기조화기"]),
            ("팬코일유닛", ["팬코일유닛"]),
            ("환기설비", ["환기설비"]),
            ("필터", ["필터"]),
            ("위생기구설비", ["위생기구설비"]),
            (
                "급수·급탕설비",
                ["급수펌프, 급탕탱크 등", "급수펌프", "급탕탱크 등"],
            ),
            ("고·저수조", ["고,저수조", "고·저수조"]),
            (
                "오·배수통기 및 우수배수설비",
                [
                    "오,배수통기 및 우수배수 설비",
                    "오·배수통기 및 우수배수 설비",
                ],
            ),
            ("오수정화설비", ["오수정화설비"]),
            ("물재이용설비", ["물 재이용설비", "물재이용설비"]),
            ("배관설비", ["배관설비"]),
            ("덕트설비", ["덕트설비"]),
            ("보온설비", ["보온설비"]),
            ("자동제어설비", ["자동제어설비"]),
            (
                "방음·방진·내진설비",
                ["방음방진내진설비", "방음·방진·내진설비"],
            ),
        ]

    def parse_standard_survey_equipment(self, tokens):
        """
        표준 조사표에서 설비명 뒤의 전체수량·점검수량을 셀 순서로 읽는다.
        같은 표가 2회 반복될 경우 첫 번째 유효 수량만 사용한다.
        """
        compact_tokens = [
            self.token_compact(token)
            for token in tokens
        ]
        results = []

        for equipment_name, labels in self.standard_equipment_definitions():
            label_keys = [
                self.token_compact(label)
                for label in labels
            ]
            found_index = -1

            for index, token_key in enumerate(compact_tokens):
                if any(
                    key and (
                        token_key == key
                        or key in token_key
                    )
                    for key in label_keys
                ):
                    found_index = index
                    break

            if found_index < 0:
                continue

            equipment_row = self.find_equipment_row(
                equipment_name
            )
            if equipment_row < 0:
                continue

            equipment = self._equipment_list[equipment_row]
            quantities = []

            # 표 구조상 설비명 뒤에 전체수량, 점검수량, 점검비율이 위치한다.
            # 비고의 연도·동력값까지 넘어가지 않도록 최대 7셀만 검사한다.
            for next_index in range(
                found_index + 1,
                min(found_index + 8, len(tokens)),
            ):
                token = tokens[next_index]

                # 비율 또는 비고가 시작되면 수량 탐색 종료
                if self.token_compact(token) in {
                    "전체",
                    "헤더포함",
                    "비고",
                }:
                    if quantities:
                        break

                parsed = self.quantity_from_token(token)
                if not parsed:
                    continue

                number, unit = parsed

                # 점검비율 20, 50, 100은 단위 없는 숫자이므로 제외
                if not unit and number in {10, 20, 50, 100}:
                    continue

                # 문서 내 연도·용량이 수량으로 섞이는 것을 방지
                if 1900 <= number <= 2100:
                    continue

                if unit in {"대", "식", "개", "개층"}:
                    quantities.append((number, unit))

                if len(quantities) >= 2:
                    break

            if equipment.get("unit") == "식":
                # 이 조사표의 1식 설비는 점검수량 셀이 '식'만 기재되기도 한다.
                total = quantities[0][0] if quantities else 1
                inspection = (
                    quantities[1][0]
                    if len(quantities) >= 2
                    else 1
                )
            else:
                total = quantities[0][0] if quantities else 0

                if len(quantities) >= 2:
                    inspection = quantities[1][0]
                elif total > 0:
                    inspection = max(
                        1,
                        math.ceil(
                            total
                            * equipment["rate"]
                            / 100
                        ),
                    )
                else:
                    inspection = 0

            results.append(
                {
                    "설비명": equipment_name,
                    "전체수량": total,
                    "점검수량": inspection,
                    "원문설비명": tokens[found_index],
                }
            )

        return results

    def survey_find_equipment_matches(self, lines):
        """HWP 표처럼 설비명과 수량이 분리된 자료도 찾아낸다."""
        matches = []
        compact_lines = [
            self.survey_compact_text(line)
            for line in lines
        ]

        for equipment_name, aliases in self._survey_equipment_aliases.items():
            found_index = -1
            found_alias = ""

            for index in range(len(lines)):
                # 같은 셀뿐 아니라 인접 셀 3개를 이어서 검색
                window = "".join(
                    compact_lines[index:min(index + 4, len(lines))]
                )

                for alias in aliases:
                    alias_key = self.survey_compact_text(alias)
                    if alias_key and alias_key in window:
                        found_index = index
                        found_alias = alias
                        break

                if found_index >= 0:
                    break

            if found_index < 0:
                continue

            # 설비명 앞뒤 셀에서 수량을 찾는다.
            nearby_lines = lines[
                max(0, found_index - 1):
                min(len(lines), found_index + 9)
            ]
            nearby_text = " ".join(nearby_lines)

            unit_numbers = re.findall(
                r"(\d+(?:,\d{3})*)\s*(?:대|식|개층|개)",
                nearby_text,
            )

            # 표 셀에서 숫자와 단위가 분리된 경우를 위한 숫자 토큰
            plain_numbers = re.findall(
                r"(?<!\d)(\d{1,5})(?!\d)",
                nearby_text,
            )

            candidates = unit_numbers or plain_numbers

            matches.append(
                {
                    "설비명": equipment_name,
                    "인식별칭": found_alias,
                    "위치": found_index,
                    "수량후보": candidates,
                    "근접내용": nearby_text,
                }
            )

        return matches

    def survey_value_after_label(self, lines, labels):
        for index, line in enumerate(lines):
            for label in labels:
                if label not in line:
                    continue

                after = line.split(label, 1)[1]
                after = re.sub(
                    r"^[\s:：\-]+",
                    "",
                    after,
                ).strip()

                if after:
                    return after

                for next_index in range(
                    index + 1,
                    min(index + 3, len(lines)),
                ):
                    if lines[next_index].strip():
                        return lines[next_index].strip()

        return ""

    def find_equipment_row(self, equipment_name):
        for row, equipment in enumerate(self._equipment_list):
            if equipment["name"] == equipment_name:
                return row
        return -1

    @staticmethod
    def survey_parse_date(text):
        match = re.search(
            r"(\d{4})\s*[.\-/년]\s*(\d{1,2})"
            r"(?:\s*[.\-/월]\s*(\d{1,2}))?",
            str(text),
        )

        if not match:
            return ""

        year = int(match.group(1))
        month = int(match.group(2))
        day = int(match.group(3) or 1)

        date_value = QDate(year, month, day)
        if not date_value.isValid():
            return ""

        return date_value.toString("yyyy-MM-dd")

    @staticmethod
    def survey_parse_floors(text):
        ground = 0
        basement = 0

        ground_match = re.search(
            r"(?:지상|지상층)\s*(\d+)",
            str(text),
        )
        basement_match = re.search(
            r"(?:지하|지하층)\s*(\d+)",
            str(text),
        )

        if ground_match:
            ground = int(ground_match.group(1))
        if basement_match:
            basement = int(basement_match.group(1))

        return ground, basement

    @staticmethod
    def survey_extract_grade(text):
        for grade in ["특급", "고급", "중급", "초급", "보조"]:
            if grade in str(text):
                return grade
        return ""
