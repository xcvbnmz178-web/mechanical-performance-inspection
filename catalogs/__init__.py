"""Application-wide catalog data."""

from .checklist import REPORT_CHECKLIST_ITEMS
from .equipment import EQUIPMENT_LIST
from .equipment_subtypes import (
    CHILLER_SUBTYPES,
    chiller_subtype_info,
    is_chiller_absorption,
    is_chiller_combustion,
    is_chiller_electric_compression,
    normalize_chiller_subtype,
)
from .inspection import FINAL_JUDGMENT_OPTIONS, INSPECTION_DB, PERFORMANCE_CALC_DEFS
from .lifespan import LIFESPAN_BY_EQUIPMENT, LIFESPAN_SOURCE_OPTIONS
from .review import (
    DESIGN_MEASURE_REVIEW_KEYWORDS,
    GUIDELINE_DOCUMENTS,
    OPERATION_REVIEW_KEYWORDS,
    SYSTEM_REVIEW_FIXED_ROWS,
)
from .staff import STAFF_LIST

__all__ = [
    "DESIGN_MEASURE_REVIEW_KEYWORDS", "EQUIPMENT_LIST",
    "CHILLER_SUBTYPES", "chiller_subtype_info",
    "FINAL_JUDGMENT_OPTIONS", "GUIDELINE_DOCUMENTS", "INSPECTION_DB",
    "LIFESPAN_BY_EQUIPMENT", "LIFESPAN_SOURCE_OPTIONS",
    "OPERATION_REVIEW_KEYWORDS", "PERFORMANCE_CALC_DEFS",
    "REPORT_CHECKLIST_ITEMS", "STAFF_LIST", "SYSTEM_REVIEW_FIXED_ROWS",
    "is_chiller_absorption", "is_chiller_combustion",
    "is_chiller_electric_compression", "normalize_chiller_subtype",
]
