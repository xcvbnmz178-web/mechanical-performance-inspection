"""Pure repeat-section planning for target and inspection-item output."""

from dataclasses import dataclass, field
from typing import Any

from .model import EquipmentEntry, InspectionItemResult, ReportDocument
from .template_contract import RepeatColumnContract, RepeatSectionContract


@dataclass(frozen=True)
class RepeatItemRow:
    equipment_id: str
    target_key: str
    item_no: str
    item_name: str
    values: tuple[str, ...]


@dataclass
class TargetRepeatBlock:
    equipment_id: str
    target_key: str
    equipment_type: str
    management_no: str
    location: str
    specification: str
    target_label: str
    item_rows: list[RepeatItemRow] = field(default_factory=list)


@dataclass
class RepeatRenderPlan:
    section_name: str
    marker_start: str
    columns: tuple[RepeatColumnContract, ...]
    targets: list[TargetRepeatBlock] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _text(value: Any) -> str:
    return "" if value is None else str(value)


def _item_value(item: InspectionItemResult, path: str) -> str:
    current: Any = item
    for part in path.split("."):
        current = getattr(current, part, "")
    return _text(current)


def build_repeat_render_plan(
    document: ReportDocument,
    contract: RepeatSectionContract,
) -> RepeatRenderPlan:
    """Build target-isolated rows without changing or merging report data."""
    plan = RepeatRenderPlan(
        section_name=contract.section_name,
        marker_start=contract.marker_start,
        columns=contract.item_template,
    )
    if contract.source_path != "targets":
        plan.warnings.append(
            f"지원하지 않는 반복 source_path: {contract.source_path}"
        )
        return plan

    equipment_by_id: dict[str, EquipmentEntry] = {
        item.equipment_id: item
        for item in document.equipment
        if item.equipment_id
    }
    for target in document.targets:
        equipment = equipment_by_id.get(target.equipment_id)
        if target.equipment_id and equipment is None:
            plan.warnings.append(
                f"{target.target_key}: equipment_id 장비대장 매칭 실패"
            )
        management_no = target.management_no_snapshot or (
            equipment.management_no if equipment else ""
        )
        block = TargetRepeatBlock(
            equipment_id=target.equipment_id,
            target_key=target.target_key,
            equipment_type=target.equipment_type,
            management_no=management_no,
            location=equipment.location if equipment else "",
            specification=equipment.specification if equipment else "",
            target_label=target.target_label,
        )
        if not target.inspection_items:
            plan.warnings.append(
                f"{target.target_key}: 점검항목이 없는 target을 빈 표로 출력"
            )
        for item in target.inspection_items:
            block.item_rows.append(
                RepeatItemRow(
                    equipment_id=target.equipment_id,
                    target_key=target.target_key,
                    item_no=item.item_no,
                    item_name=item.item_name,
                    values=tuple(
                        _item_value(item, column.source_path)
                        for column in contract.item_template
                    ),
                )
            )
        plan.targets.append(block)
    return plan
