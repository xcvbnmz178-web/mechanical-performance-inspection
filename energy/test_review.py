import unittest

from energy.service import (
    build_energy_report_view,
    build_energy_review_data,
    format_energy_review_summary,
)


def rows(years, electricity=None, gas=None):
    electricity = electricity or []
    gas = gas or []
    result = []
    for index, year in enumerate(years):
        if index < len(gas):
            result.append({"연도": str(year), "종류": "가스", "단위": "N㎥", "총 사용량": str(gas[index])})
        if index < len(electricity):
            result.append({"연도": str(year), "종류": "전기", "단위": "kWh", "총 사용량": str(electricity[index])})
    return result


class EnergyReviewTests(unittest.TestCase):
    def test_zero_years_is_data_insufficient(self):
        review = build_energy_review_data([])
        self.assertEqual(review["technical_status"], "data_insufficient")

    def test_one_year_is_safe_and_not_comparable(self):
        review = build_energy_review_data(rows([2026], [100], [50]))
        self.assertEqual(review["technical_status_label"], "데이터부족/비교불가")
        self.assertIsNone(review["comparisons"]["total_toe"]["change_rate"])

    def test_two_year_increase_is_cause_review_not_fail(self):
        review = build_energy_review_data(rows([2025, 2026], [100, 110], [100, 110]))
        self.assertEqual(review["technical_status_label"], "증가원인확인")
        self.assertNotIn("fail", review)
        self.assertNotIn("judgment", review)

    def test_three_year_normal_and_units_stay_separate(self):
        review = build_energy_review_data(rows([2024, 2025, 2026], [100, 101, 102], [50, 50, 50]))
        self.assertEqual(review["technical_status_label"], "데이터 정상")
        self.assertEqual(review["units"]["electricity_usage"], "kWh")
        self.assertEqual(review["units"]["gas_usage"], "N㎥")
        self.assertEqual(len(review["series"]["total_toe"]), 3)
        text = format_energy_review_summary(review)
        self.assertIn("전력사용량", text)
        self.assertIn("도시가스사용량", text)
        self.assertIn("총 TOE", text)

    def test_supported_sources_work_independently(self):
        cases = [
            ("전력사용량", "electricity", "kWh"),
            ("도시가스사용량", "city_gas", "N㎥"),
            ("지역난방 난방사용량", "district_heating", "Gcal"),
            ("지역난방 냉방사용량", "district_cooling", "Gcal"),
            ("지역난방 총사용량", "district_total", "Gcal"),
            ("바이오매스", "other:바이오매스", "ton"),
        ]
        for name, key, unit in cases:
            review = build_energy_review_data([
                {"연도": "2025", "종류": name, "단위": unit, "총 사용량": "10"},
                {"연도": "2026", "종류": name, "단위": unit, "총 사용량": "11"},
            ])
            self.assertIn(key, review["series_by_type"])

    def test_district_total_is_derived_only_for_same_unit(self):
        review = build_energy_review_data([
            {"연도": "2025", "종류": "난방사용량", "단위": "Gcal", "총 사용량": "10"},
            {"연도": "2025", "종류": "냉방사용량", "단위": "Gcal", "총 사용량": "4"},
        ])
        total = review["series_by_type"]["district_total"]
        self.assertEqual(total["yearly_values"]["2025"], 14.0)
        self.assertIn("동일 단위", total["source_note"])
        mixed = build_energy_review_data([
            {"연도": "2025", "종류": "난방사용량", "단위": "Gcal", "총 사용량": "10"},
            {"연도": "2025", "종류": "냉방사용량", "단위": "MWh", "총 사용량": "4"},
        ])
        self.assertNotIn("district_total", mixed["series_by_type"])

    def test_raw_district_total_has_priority(self):
        review = build_energy_review_data([
            {"연도": "2025", "종류": "난방사용량", "단위": "Gcal", "총 사용량": "10"},
            {"연도": "2025", "종류": "냉방사용량", "단위": "Gcal", "총 사용량": "4"},
            {"연도": "2025", "종류": "지역난방 총사용량", "단위": "Gcal", "총 사용량": "20"},
        ])
        total = review["series_by_type"]["district_total"]
        self.assertEqual(total["yearly_values"]["2025"], 20.0)
        self.assertEqual(total["source_note"], "관리주체 제공자료")

    def test_missing_middle_year_is_not_zero(self):
        review = build_energy_review_data([
            {"연도": "2024", "종류": "전력사용량", "단위": "kWh", "총 사용량": "100"},
            {"연도": "2026", "종류": "전력사용량", "단위": "kWh", "총 사용량": "110"},
        ])
        comparison = review["comparisons"]["electricity"]
        self.assertEqual((comparison["from_year"], comparison["to_year"]), ("2024", "2026"))
        self.assertEqual(comparison["change"], 10.0)
        text = format_energy_review_summary(review)
        self.assertIn("직전 보유자료(2024년) 대비", text)
        self.assertNotIn("2025년", text)

    def test_formatter_uses_latest_three_actual_years(self):
        review = build_energy_review_data([
            {"연도": str(year), "종류": "전력사용량", "단위": "kWh", "총 사용량": str(value)}
            for year, value in ((2022, 80), (2023, 90), (2024, 100), (2025, 95), (2026, 102))
        ])
        text = format_energy_review_summary(review)
        self.assertNotIn("2022년", text)
        self.assertNotIn("2023년", text)
        for year in ("2024년", "2025년", "2026년"):
            self.assertIn(year, text)
        self.assertIn("전년 대비", text)

    def test_one_year_formatter_explains_no_comparison(self):
        review = build_energy_review_data([
            {"연도": "2026", "종류": "도시가스사용량", "단위": "N㎥", "총 사용량": "50"}
        ])
        self.assertIn("비교 가능한 이전 연도 자료가 없음", format_energy_review_summary(review))

    def test_same_source_with_different_units_is_separated(self):
        review = build_energy_review_data([
            {"연도": "2025", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "10"},
            {"연도": "2026", "종류": "지역난방 난방사용량", "단위": "MWh", "총 사용량": "5"},
        ])
        self.assertIn("district_heating", review["series_by_type"])
        self.assertIn("district_heating@MWh", review["series_by_type"])

    def test_explicit_toe_and_nonconvertible_data_can_coexist(self):
        review = build_energy_review_data([
            {"연도": "2025", "종류": "전력사용량", "단위": "kWh", "총 사용량": "100"},
            {"연도": "2025", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "20"},
            {"연도": "2025", "종류": "바이오매스", "단위": "ton", "총 사용량": "3", "TOE/년": "2"},
        ])
        self.assertFalse(review["series_by_type"]["district_heating"]["yearly_toe"])
        self.assertEqual(review["series_by_type"]["other:바이오매스"]["yearly_toe"]["2025"], 2.0)
        self.assertGreater(review["total_toe"]["2025"], 2.0)

    def test_report_view_reuses_exact_sample_values_and_rates(self):
        review = build_energy_review_data(rows(
            [2024, 2025, 2026], [200, 220, 250], [100, 120, 110]
        ))
        view = build_energy_report_view(review)
        electricity = [
            row for row in view["detail_rows"]
            if row["energy_type"] == "electricity"
        ]
        gas = [
            row for row in view["detail_rows"]
            if row["energy_type"] == "city_gas"
        ]
        self.assertAlmostEqual(electricity[-1]["change_rate"], 13.6363636)
        self.assertAlmostEqual(gas[-1]["change_rate"], -8.3333333)
        self.assertIn("+13.64%", view["overview_text"])
        self.assertIn("-8.33%", view["overview_text"])

    def test_report_view_latest_three_gap_zero_and_district(self):
        review = build_energy_review_data([
            {"연도": "2020", "종류": "전력사용량", "단위": "kWh", "총 사용량": "70"},
            {"연도": "2022", "종류": "전력사용량", "단위": "kWh", "총 사용량": "80"},
            {"연도": "2024", "종류": "전력사용량", "단위": "kWh", "총 사용량": "0"},
            {"연도": "2026", "종류": "전력사용량", "단위": "kWh", "총 사용량": "100"},
            {"연도": "2026", "종류": "지역난방 난방사용량", "단위": "Gcal", "총 사용량": "20"},
        ])
        view = build_energy_report_view(review)
        self.assertNotIn("2020년", view["overview_text"])
        self.assertIn("비교불가", view["overview_text"])
        self.assertIn("지역난방 난방사용량", view["overview_text"])


if __name__ == "__main__":
    unittest.main()
