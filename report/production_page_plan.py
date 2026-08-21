"""Deterministic page planning for the production HWP report."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from .production_model import ProductionInspectionItemView, ProductionReportView


FRONT_PAGE_COUNT = 18
INSPECTION_ITEMS_PER_PAGE = 7
DETAIL_ITEMS_PER_PAGE = 3


@dataclass(frozen=True)
class ProductionTargetPagePlan:
    target_index: int
    item_count: int
    inspection_page_count: int
    detail_page_count: int
    inspection_start_page: int
    detail_start_page: int
    inspection_item_ranges: tuple[tuple[int, int], ...]
    detail_item_ranges: tuple[tuple[int, int], ...]

    @property
    def total_page_count(self) -> int:
        return self.inspection_page_count + self.detail_page_count


@dataclass(frozen=True)
class ProductionPagePlan:
    front_page_count: int
    target_plans: tuple[ProductionTargetPagePlan, ...]
    extension_page_count: int = 0

    @property
    def total_page_count(self) -> int:
        return (
            self.front_page_count
            + sum(plan.total_page_count for plan in self.target_plans)
            + self.extension_page_count
        )


def _line_count(value: str, column_width: int) -> int:
    return max(1, ceil(len(str(value or "")) / column_width))


def _inspection_weight(item: ProductionInspectionItemView) -> int:
    return max(
        _line_count(item.item_name, 12),
        _line_count(item.inspection_method, 13),
        _line_count(item.inspection_criteria, 18),
        _line_count(item.reference_value, 10),
        _line_count(item.measured_value, 10),
        _line_count(item.technical_note, 15),
    )


def _detail_weight(item: ProductionInspectionItemView) -> int:
    return max(
        _line_count(item.inspection_method, 34),
        _line_count(item.inspection_criteria, 35),
        _line_count(item.reference_value, 30),
        _line_count(item.measured_value, 30),
        _line_count(item.technical_note, 35),
    ) + (5 if item.photos else 0)


def _item_ranges(
    items: tuple[ProductionInspectionItemView, ...],
    *,
    max_items: int,
    max_weight: int,
    weight_fn,
) -> tuple[tuple[int, int], ...]:
    if not items:
        return ((0, 0),)
    ranges = []
    start = 0
    weight = 0
    for index, item in enumerate(items):
        item_weight = weight_fn(item)
        if index > start and (index - start >= max_items or weight + item_weight > max_weight):
            ranges.append((start, index))
            start = index
            weight = 0
        weight += item_weight
    ranges.append((start, len(items)))
    return tuple(ranges)


def plan_production_pages(view: ProductionReportView) -> ProductionPagePlan:
    """Calculate every target page before rendering starts."""
    target_plans = []
    next_page = FRONT_PAGE_COUNT + 1
    for target_index, target in enumerate(view.targets):
        item_count = len(target.items)
        inspection_ranges = _item_ranges(
            target.items,
            max_items=INSPECTION_ITEMS_PER_PAGE,
            max_weight=13,
            weight_fn=_inspection_weight,
        )
        detail_ranges = _item_ranges(
            target.items,
            max_items=DETAIL_ITEMS_PER_PAGE,
            max_weight=10,
            weight_fn=_detail_weight,
        )
        inspection_pages = len(inspection_ranges)
        detail_pages = len(detail_ranges)
        detail_start = next_page + inspection_pages
        target_plans.append(
            ProductionTargetPagePlan(
                target_index=target_index,
                item_count=item_count,
                inspection_page_count=inspection_pages,
                detail_page_count=detail_pages,
                inspection_start_page=next_page,
                detail_start_page=detail_start,
                inspection_item_ranges=inspection_ranges,
                detail_item_ranges=detail_ranges,
            )
        )
        next_page = detail_start + detail_pages
    return ProductionPagePlan(FRONT_PAGE_COUNT, tuple(target_plans))
