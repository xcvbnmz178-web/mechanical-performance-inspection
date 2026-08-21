"""Reusable energy-source analysis independent from Qt and report output."""

from dataclasses import asdict, dataclass, field


DEFAULT_GAS_TOE_FACTOR = 0.001019
DEFAULT_ELECTRIC_TOE_FACTOR = 0.000229
TOE_TO_KWH = 11630.0


ENERGY_TYPE_DEFINITIONS = {
    "electricity": {
        "display_name": "전력사용량",
        "aliases": {"전기", "전력", "전력사용량", "전기사용량"},
        "default_unit": "kWh",
        "default_factor": DEFAULT_ELECTRIC_TOE_FACTOR,
        "color": "#2563eb",
    },
    "city_gas": {
        "display_name": "도시가스사용량",
        "aliases": {"가스", "도시가스", "도시가스사용량", "가스사용량"},
        "default_unit": "N㎥",
        "default_factor": DEFAULT_GAS_TOE_FACTOR,
        "color": "#d97706",
    },
    "district_heating": {
        "display_name": "지역난방 난방사용량",
        "aliases": {"난방사용량", "지역난방 난방사용량", "지역난방난방"},
        "default_unit": "Gcal",
        "default_factor": None,
        "color": "#dc2626",
    },
    "district_cooling": {
        "display_name": "지역난방 냉방사용량",
        "aliases": {"냉방사용량", "지역난방 냉방사용량", "지역난방냉방"},
        "default_unit": "Gcal",
        "default_factor": None,
        "color": "#0891b2",
    },
    "district_total": {
        "display_name": "지역난방 총사용량",
        "aliases": {"지역난방 총사용량", "지역난방총사용량", "총 열사용량"},
        "default_unit": "Gcal",
        "default_factor": None,
        "color": "#7c3aed",
    },
}


@dataclass
class EnergySeries:
    energy_type: str
    display_name: str
    unit: str
    yearly_values: dict[str, float] = field(default_factory=dict)
    yearly_toe: dict[str, float] = field(default_factory=dict)
    source_note: str = "관리주체 제공자료"
    toe_factor: float | None = None
    color: str = "#4b5563"


@dataclass
class EnergyReviewSummary:
    series: list[EnergySeries]
    total_toe: dict[str, float]
    latest_change: dict[str, float | None]
    latest_change_rate: dict[str, float | None]
    review_status: str
    review_status_label: str
    review_note: str
    increase_review_pct: float = 5.0


def _number(value):
    try:
        return float(str(value or "").replace(",", "").strip() or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_number(value):
    text = str(value or "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_energy_type(value):
    raw = str(value or "").strip()
    compact = raw.replace(" ", "")
    for key, definition in ENERGY_TYPE_DEFINITIONS.items():
        if raw in definition["aliases"] or compact in {
            alias.replace(" ", "") for alias in definition["aliases"]
        }:
            return key, definition
    key = "other:" + (raw or "기타")
    return key, {
        "display_name": raw or "기타 에너지원",
        "aliases": {raw},
        "default_unit": "",
        "default_factor": None,
        "color": "#4b5563",
    }


def _comparison(yearly_values):
    points = sorted(yearly_values.items())
    if len(points) < 2:
        return {"from_year": "", "to_year": "", "change": None, "change_rate": None}
    (from_year, previous), (to_year, current) = points[-2], points[-1]
    return {
        "from_year": from_year,
        "to_year": to_year,
        "change": current - previous,
        "change_rate": ((current - previous) / previous * 100.0 if previous > 0 else None),
    }


def _derive_district_total(series_by_type):
    if "district_total" in series_by_type:
        return
    heating = series_by_type.get("district_heating")
    cooling = series_by_type.get("district_cooling")
    if not heating or not cooling or heating.unit != cooling.unit:
        return
    common_years = sorted(set(heating.yearly_values) & set(cooling.yearly_values))
    if not common_years:
        return
    definition = ENERGY_TYPE_DEFINITIONS["district_total"]
    total = EnergySeries(
        energy_type="district_total",
        display_name=definition["display_name"],
        unit=heating.unit,
        source_note="원자료에 총계가 없어 동일 단위 난방사용량+냉방사용량으로 계산",
        color=definition["color"],
    )
    for year in common_years:
        total.yearly_values[year] = heating.yearly_values[year] + cooling.yearly_values[year]
        if year in heating.yearly_toe and year in cooling.yearly_toe:
            total.yearly_toe[year] = heating.yearly_toe[year] + cooling.yearly_toe[year]
    series_by_type["district_total"] = total


def build_energy_review_data(
    rows,
    gas_factor=DEFAULT_GAS_TOE_FACTOR,
    electric_factor=DEFAULT_ELECTRIC_TOE_FACTOR,
    increase_review_pct=5.0,
):
    """Interpret current and legacy energy rows without modifying them."""
    factor_overrides = {"city_gas": gas_factor, "electricity": electric_factor}
    series_by_type = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        year = str(row.get("연도", "") or "").strip()
        raw_type = row.get("종류", row.get("에너지원", ""))
        if not year or not str(raw_type or "").strip():
            continue
        key, definition = normalize_energy_type(raw_type)
        unit = str(row.get("단위", "") or definition["default_unit"]).strip()
        series = series_by_type.get(key)
        if series is None:
            factor = factor_overrides.get(key, definition["default_factor"])
            series = EnergySeries(
                energy_type=key,
                display_name=definition["display_name"],
                unit=unit,
                toe_factor=factor,
                color=definition["color"],
            )
            series_by_type[key] = series
        elif unit and series.unit != unit:
            # Never merge unlike raw units onto one series/axis.
            key = f"{key}@{unit}"
            series = series_by_type.setdefault(
                key,
                EnergySeries(
                    energy_type=key,
                    display_name=f"{definition['display_name']} ({unit})",
                    unit=unit,
                    source_note="동일 에너지원에 복수 단위가 있어 별도 시계열로 분리",
                    toe_factor=None,
                    color=definition["color"],
                ),
            )
        usage = _optional_number(row.get("총 사용량", row.get("사용량", "")))
        if usage is None:
            continue
        series.yearly_values[year] = usage
        explicit_toe = _optional_number(row.get("TOE/년", row.get("TOE", "")))
        # Registered electricity/gas factors are the source of truth. This
        # prevents a previously displayed calculated TOE cell from becoming a
        # stale input after usage or factor changes. Unregistered sources may
        # still carry an explicitly provided TOE value.
        if series.toe_factor is not None:
            series.yearly_toe[year] = usage * series.toe_factor
        elif explicit_toe is not None:
            series.yearly_toe[year] = explicit_toe

    _derive_district_total(series_by_type)
    ordered_keys = list(ENERGY_TYPE_DEFINITIONS) + sorted(
        key for key in series_by_type if key not in ENERGY_TYPE_DEFINITIONS
    )
    series_list = [series_by_type[key] for key in ordered_keys if key in series_by_type]

    total_toe = {}
    district_total = series_by_type.get("district_total")
    use_district_total_toe = bool(district_total and district_total.yearly_toe)
    for series in series_list:
        if use_district_total_toe and series.energy_type in {"district_heating", "district_cooling"}:
            continue
        if not use_district_total_toe and series.energy_type == "district_total":
            continue
        for year, toe in series.yearly_toe.items():
            total_toe[year] = total_toe.get(year, 0.0) + toe

    comparisons = {series.energy_type: _comparison(series.yearly_values) for series in series_list}
    total_comparison = _comparison(total_toe)
    comparable = [value for value in comparisons.values() if value["change_rate"] is not None]
    rates = [value["change_rate"] for value in comparable]
    if total_comparison["change_rate"] is not None:
        rates.append(total_comparison["change_rate"])
    if not series_list:
        status, label = "data_insufficient", "데이터부족/비교불가"
    elif not rates:
        status, label = "data_insufficient", "데이터부족/비교불가"
    elif any(rate >= increase_review_pct for rate in rates):
        status, label = "increase_review", "증가원인확인"
    else:
        status, label = "normal", "데이터 정상"

    latest_change = {key: value["change"] for key, value in comparisons.items()}
    latest_change_rate = {key: value["change_rate"] for key, value in comparisons.items()}
    latest_change["total_toe"] = total_comparison["change"]
    latest_change_rate["total_toe"] = total_comparison["change_rate"]
    note = (
        "개별 냉난방설비별 사용량은 별도 계량자료가 없어 "
        "관리주체 제공 에너지원별 전체 사용량을 기준으로 검토"
    )
    summary_model = EnergyReviewSummary(
        series=series_list,
        total_toe=total_toe,
        latest_change=latest_change,
        latest_change_rate=latest_change_rate,
        review_status=status,
        review_status_label=label,
        review_note=note,
        increase_review_pct=increase_review_pct,
    )

    years = sorted({year for series in series_list for year in series.yearly_values})
    # Compatibility keys remain read-only views for existing UI/tests.
    electricity = series_by_type.get("electricity", EnergySeries("", "", "kWh"))
    gas = series_by_type.get("city_gas", EnergySeries("", "", "N㎥"))
    return {
        "model": summary_model,
        "energy_series": [asdict(series) for series in series_list],
        "series_by_type": {series.energy_type: asdict(series) for series in series_list},
        "years": years,
        "total_toe": total_toe,
        "comparisons": comparisons | {"total_toe": total_comparison},
        "technical_status": status,
        "technical_status_label": label,
        "review_note": note,
        "increase_review_pct": increase_review_pct,
        "series": {
            "electricity_usage": [electricity.yearly_values.get(year) for year in years],
            "gas_usage": [gas.yearly_values.get(year) for year in years],
            "electricity_toe": [electricity.yearly_toe.get(year) for year in years],
            "gas_toe": [gas.yearly_toe.get(year) for year in years],
            "total_toe": [total_toe.get(year) for year in years],
        },
        "units": {"electricity_usage": "kWh", "gas_usage": "N㎥", "toe": "TOE"},
    }


def _energy_year_sort_key(value):
    text = str(value)
    try:
        return (0, int(text))
    except ValueError:
        return (1, text)


def _is_consecutive_year(previous, current):
    try:
        return int(current) - int(previous) == 1
    except (TypeError, ValueError):
        return False


def format_energy_three_year_review(review):
    """Format latest actual three years for UI, reports, and HWP adapters."""
    series_list = review.get("energy_series", [])
    if not series_list:
        return "데이터부족/비교불가: 관리주체 제공 에너지원별 사용량 자료가 없습니다."
    lines = [review.get("review_note", "")]
    for series in series_list:
        values = series["yearly_values"]
        source = series.get("source_note", "")
        years = sorted(values, key=_energy_year_sort_key)[-3:]
        lines.append(f"[{series['display_name']}]")
        previous_year = None
        previous_value = None
        for year in years:
            value = values[year]
            suffix = ""
            if previous_year is not None:
                change = value - previous_value
                rate = change / previous_value * 100.0 if previous_value > 0 else None
                comparison_name = (
                    "전년 대비"
                    if _is_consecutive_year(previous_year, year)
                    else f"직전 보유자료({previous_year}년) 대비"
                )
                if rate is None:
                    suffix = f" ({comparison_name} 증감률 비교불가)"
                else:
                    suffix = (
                        f" ({comparison_name} {change:+,.2f}{series['unit']}, "
                        f"{rate:+.2f}%)"
                    )
            lines.append(f"- {year}년: {value:,.2f} {series['unit']}{suffix}")
            previous_year, previous_value = year, value
        if len(years) == 1:
            lines.append("- 비교 가능한 이전 연도 자료가 없음")
        if source and source != "관리주체 제공자료":
            lines.append(f"- 산정근거: {source}")
        if series.get("yearly_toe"):
            toe_years = [year for year in years if year in series["yearly_toe"]]
            if toe_years:
                lines.append(
                    "- TOE: " + ", ".join(
                        f"{year}년 {toe:.3f}TOE"
                        for year, toe in (
                            (year, series["yearly_toe"][year]) for year in toe_years
                        )
                    )
                )
    if review.get("total_toe"):
        total_years = sorted(
            review["total_toe"], key=_energy_year_sort_key
        )[-3:]
        lines.append(
            "총 TOE: " + ", ".join(
                f"{year}년 {review['total_toe'][year]:.3f}TOE"
                for year in total_years
            )
        )
    lines.append(f"기술검토 상태: {review['technical_status_label']}")
    if review["technical_status"] == "increase_review":
        lines.append(
            f"내부 증가원인확인 기준 +{review['increase_review_pct']:.0f}% 이상인 "
            "에너지원 또는 총 TOE가 있습니다. 이는 법정 부적합이나 최종 X 판정 기준이 아닙니다."
        )
    return "\n".join(line for line in lines if line)


def format_energy_review_summary(review):
    """Backward-compatible name for the common three-year formatter."""
    return format_energy_three_year_review(review)


def build_energy_report_view(review):
    """Build report rows and compact narrative from one normalized review.

    The returned values are presentation data only. They never mutate the
    project rows and intentionally use the latest three *actual* years.
    """
    detail_rows = []
    overview_lines = []
    for series in review.get("energy_series", []):
        values = series.get("yearly_values", {})
        years = sorted(values, key=_energy_year_sort_key)[-3:]
        compact = []
        previous_year = None
        previous_value = None
        for year in years:
            value = values[year]
            change = None
            rate = None
            comparison_label = "비교기준"
            if previous_year is not None:
                change = value - previous_value
                rate = change / previous_value * 100.0 if previous_value > 0 else None
                comparison_label = (
                    "전년 대비"
                    if _is_consecutive_year(previous_year, year)
                    else f"직전 보유자료 {previous_year}년 대비"
                )
            detail_rows.append({
                "year": year,
                "energy_type": series.get("energy_type", ""),
                "display_name": series.get("display_name", ""),
                "unit": series.get("unit", ""),
                "value": value,
                "toe": series.get("yearly_toe", {}).get(year),
                "from_year": previous_year or "",
                "change": change,
                "change_rate": rate,
                "comparison_label": comparison_label,
            })
            if previous_year is None:
                compact.append(f"{year}년 {value:,.2f}")
            elif rate is None:
                compact.append(f"{year}년 {value:,.2f}(비교불가)")
            else:
                compact.append(f"{year}년 {value:,.2f}({rate:+.2f}%)")
            previous_year, previous_value = year, value
        if len(years) == 1:
            overview_lines.append(
                f"{series.get('display_name', '')}: {compact[0]} {series.get('unit', '')}. "
                "비교 가능한 이전 연도 자료가 없어 추세 분석 불가."
            )
        elif compact:
            overview_lines.append(
                f"{series.get('display_name', '')}({series.get('unit', '')}): "
                + " → ".join(compact)
            )

    total_rows = []
    total_toe = review.get("total_toe", {})
    total_years = sorted(total_toe, key=_energy_year_sort_key)[-3:]
    previous_year = None
    previous_value = None
    total_compact = []
    for year in total_years:
        value = total_toe[year]
        change = None
        rate = None
        if previous_year is not None:
            change = value - previous_value
            rate = change / previous_value * 100.0 if previous_value > 0 else None
        total_rows.append({
            "year": year,
            "value": value,
            "from_year": previous_year or "",
            "change": change,
            "change_rate": rate,
        })
        if previous_year is None:
            total_compact.append(f"{year}년 {value:.3f}")
        elif rate is None:
            total_compact.append(f"{year}년 {value:.3f}(비교불가)")
        else:
            total_compact.append(f"{year}년 {value:.3f}({rate:+.2f}%)")
        previous_year, previous_value = year, value
    if total_compact:
        overview_lines.append("총 TOE: " + " → ".join(total_compact))

    return {
        "detail_rows": detail_rows,
        "total_rows": total_rows,
        "overview_lines": overview_lines,
        "overview_text": "\n".join(overview_lines),
        "technical_status": review.get("technical_status", "data_insufficient"),
        "technical_status_label": review.get(
            "technical_status_label", "데이터부족/비교불가"
        ),
        "review_note": review.get("review_note", ""),
    }


def calculate_toe(usage, factor):
    return usage * factor


def calculate_composition_ratio(toe, total_toe):
    return toe / total_toe * 100 if total_toe else 0


def calculate_change_rate(current, previous):
    if previous is None or previous <= 0:
        return None
    return (current - previous) / previous * 100


def calculate_primary_intensity(toe, denominator):
    return toe * TOE_TO_KWH / denominator if denominator else 0
