from .service import (
    DEFAULT_ELECTRIC_TOE_FACTOR,
    DEFAULT_GAS_TOE_FACTOR,
    ENERGY_TYPE_DEFINITIONS,
    EnergyReviewSummary,
    EnergySeries,
    TOE_TO_KWH,
    build_energy_review_data,
    build_energy_report_view,
    calculate_change_rate,
    calculate_composition_ratio,
    calculate_primary_intensity,
    calculate_toe,
    format_energy_review_summary,
    format_energy_three_year_review,
    normalize_energy_type,
)


def __getattr__(name):
    """Keep the Qt manager lazy so report/service consumers stay Qt-independent."""
    if name == "EnergyManagerMixin":
        from .manager import EnergyManagerMixin
        return EnergyManagerMixin
    raise AttributeError(name)

__all__ = [
    "DEFAULT_ELECTRIC_TOE_FACTOR",
    "DEFAULT_GAS_TOE_FACTOR",
    "ENERGY_TYPE_DEFINITIONS",
    "EnergyReviewSummary",
    "EnergySeries",
    "EnergyManagerMixin",
    "TOE_TO_KWH",
    "build_energy_review_data",
    "build_energy_report_view",
    "calculate_change_rate",
    "calculate_composition_ratio",
    "calculate_primary_intensity",
    "calculate_toe",
    "format_energy_review_summary",
    "format_energy_three_year_review",
    "normalize_energy_type",
]
