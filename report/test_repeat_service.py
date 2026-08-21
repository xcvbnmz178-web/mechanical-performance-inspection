import tempfile
import unittest
from pathlib import Path

from report.hwp_adapter import HwpAdapterError, TemplateContractError
from report.hwp_repeat_adapter import HwpReportAdapter
from report.model import (
    EquipmentEntry,
    InspectionItemResult,
    InspectionTargetSection,
    ReportDocument,
    SiteSection,
)
from report.repeat_service import build_repeat_render_plan
from report.template_contract import (
    MINIMAL_REPEAT_HWP_CONTRACT,
    TARGET_REPEAT_SECTION,
    validate_template_contract,
)
from report.test_template_contract import FakeHwp


def make_item(index, suffix=""):
    return InspectionItemResult(
        item_no=str(index),
        item_name=f"점검항목 {index}",
        inspection_method=f"방법 {index}",
        inspection_criteria=f"기준 {index}{suffix}",
        measured_value=f"측정 {index}",
        judgment=f"판정 {index}",
        technical_note=f"소견 {index}",
    )


def make_document(target_count=1, item_count=2, same_equipment=False):
    equipment = []
    targets = []
    for target_index in range(target_count):
        equipment_index = 0 if same_equipment else target_index
        equipment_id = f"equipment-{equipment_index}"
        if not any(item.equipment_id == equipment_id for item in equipment):
            equipment.append(
                EquipmentEntry(
                    equipment_id=equipment_id,
                    equipment_type="냉동기",
                    management_no=f"CH-{equipment_index + 1:02d}",
                    location=f"기계실 {equipment_index + 1}",
                    specification=f"사양 {equipment_index + 1}",
                )
            )
        targets.append(
            InspectionTargetSection(
                target_key=f"냉동기|{target_index + 1}|{equipment_index}|{target_index}",
                equipment_id=equipment_id,
                equipment_type="냉동기",
                management_no_snapshot=f"CH-{equipment_index + 1:02d}",
                target_label=f"냉동기 점검 {target_index + 1}",
                inspection_items=[make_item(index + 1) for index in range(item_count)],
            )
        )
    return ReportDocument(
        site=SiteSection(
            {
                "현장명": "테스트 현장",
                "주소": "인천광역시",
                "관리주체": "관리사무소",
                "점검시작일": "2026-08-01",
                "점검종료일": "2026-08-02",
                "보고서작성일": "2026-08-10",
                "용도": "공동주택",
            }
        ),
        equipment=equipment,
        targets=targets,
    )


class FakeRepeatWriter:
    instances = []

    def __init__(self, _hwp):
        self.calls = []
        self.__class__.instances.append(self)

    def insert_plan(self, plan, page_break_between):
        self.calls.append((plan, page_break_between))


class FailingRepeatWriter(FakeRepeatWriter):
    def insert_plan(self, plan, page_break_between):
        raise HwpAdapterError("repeat failed")


class RepeatServiceTests(unittest.TestCase):
    def test_target_counts_one_two_five(self):
        for count in (1, 2, 5):
            with self.subTest(count=count):
                plan = build_repeat_render_plan(
                    make_document(count, 2), TARGET_REPEAT_SECTION
                )
                self.assertEqual(len(plan.targets), count)
                self.assertEqual([len(block.item_rows) for block in plan.targets], [2] * count)

    def test_same_equipment_multiple_targets_remain_separate(self):
        plan = build_repeat_render_plan(
            make_document(2, 2, same_equipment=True), TARGET_REPEAT_SECTION
        )
        self.assertEqual(plan.targets[0].equipment_id, plan.targets[1].equipment_id)
        self.assertNotEqual(plan.targets[0].target_key, plan.targets[1].target_key)
        self.assertEqual(len(plan.targets), 2)

    def test_two_and_fifteen_variable_rows(self):
        for count in (2, 15):
            plan = build_repeat_render_plan(make_document(1, count), TARGET_REPEAT_SECTION)
            self.assertEqual(len(plan.targets[0].item_rows), count)

    def test_identity_prevents_same_item_number_and_name_mixing(self):
        document = make_document(2, 1)
        document.targets[0].inspection_items[0].item_name = "동일 항목"
        document.targets[1].inspection_items[0].item_name = "동일 항목"
        document.targets[0].inspection_items[0].judgment = "○ 합격"
        document.targets[1].inspection_items[0].judgment = "X 불합격"
        plan = build_repeat_render_plan(document, TARGET_REPEAT_SECTION)
        first, second = plan.targets[0].item_rows[0], plan.targets[1].item_rows[0]
        self.assertNotEqual(first.target_key, second.target_key)
        self.assertIn("○ 합격", first.values)
        self.assertIn("X 불합격", second.values)

    def test_long_criteria_is_not_truncated(self):
        long_text = "긴 점검기준 " * 500
        document = make_document(1, 1)
        document.targets[0].inspection_items[0].inspection_criteria = long_text
        plan = build_repeat_render_plan(document, TARGET_REPEAT_SECTION)
        self.assertIn(long_text, plan.targets[0].item_rows[0].values)

    def test_empty_target_is_kept_with_warning(self):
        plan = build_repeat_render_plan(make_document(1, 0), TARGET_REPEAT_SECTION)
        self.assertEqual(len(plan.targets), 1)
        self.assertEqual(plan.targets[0].item_rows, [])
        self.assertTrue(any("빈 표" in warning for warning in plan.warnings))

    def test_missing_repeat_anchor_is_contract_error(self):
        fields = {
            field.field_name for field in MINIMAL_REPEAT_HWP_CONTRACT.fields
        }
        result = validate_template_contract(
            make_document(), MINIMAL_REPEAT_HWP_CONTRACT, fields
        )
        self.assertFalse(result.valid)
        self.assertTrue(any("anchor" in error for error in result.errors))


class RepeatAdapterTests(unittest.TestCase):
    def fields(self):
        return {
            field.field_name for field in MINIMAL_REPEAT_HWP_CONTRACT.fields
        } | {TARGET_REPEAT_SECTION.marker_start}

    def test_adapter_passes_five_isolated_targets(self):
        FakeRepeatWriter.instances.clear()
        fake_hwp = FakeHwp(self.fields())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "repeat.hwp"
            output = root / "output.hwp"
            template.write_bytes(b"repeat-template")
            original = template.read_bytes()
            result = HwpReportAdapter(
                lambda: fake_hwp, FakeRepeatWriter
            ).generate(
                make_document(5, 2),
                MINIMAL_REPEAT_HWP_CONTRACT,
                template,
                output,
            )
            self.assertEqual(template.read_bytes(), original)
            self.assertTrue(output.is_file())
            plan, page_break = FakeRepeatWriter.instances[0].calls[0]
            self.assertEqual(len(plan.targets), 5)
            self.assertTrue(page_break)
            self.assertEqual(len({block.target_key for block in plan.targets}), 5)
            self.assertEqual(result.output_path, str(output.resolve()))

    def test_anchor_missing_stops_before_repeat(self):
        FakeRepeatWriter.instances.clear()
        fake_hwp = FakeHwp(self.fields() - {TARGET_REPEAT_SECTION.marker_start})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "repeat.hwp"
            template.write_bytes(b"repeat-template")
            with self.assertRaises(TemplateContractError):
                HwpReportAdapter(lambda: fake_hwp, FakeRepeatWriter).generate(
                    make_document(), MINIMAL_REPEAT_HWP_CONTRACT, template, root / "out.hwp"
                )
            self.assertEqual(FakeRepeatWriter.instances, [])

    def test_repeat_failure_removes_temporary_file(self):
        fake_hwp = FakeHwp(self.fields())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template = root / "repeat.hwp"
            template.write_bytes(b"repeat-template")
            with self.assertRaises(HwpAdapterError):
                HwpReportAdapter(lambda: fake_hwp, FailingRepeatWriter).generate(
                    make_document(), MINIMAL_REPEAT_HWP_CONTRACT, template, root / "out.hwp"
                )
            self.assertEqual(list(root.glob(".out_*.hwp")), [])
            self.assertTrue(fake_hwp.quit_called)


if __name__ == "__main__":
    unittest.main()
