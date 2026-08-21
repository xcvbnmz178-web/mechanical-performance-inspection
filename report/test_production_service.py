import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from report.hwp_production_renderer import HwpProductionRenderer
from report.production_model import ProductionCompanyView
from report.production_page_plan import plan_production_pages
from report.production_service import generate_production_hwp, prepare_production_report
from report.production_view import (
    FORBIDDEN_CUSTOMER_TOKENS,
    assert_summary_detail_consistency,
    customer_visible_text,
    validate_customer_visible_text,
)


def _sample_png(width=320, height=180):
    raw = b"".join(b"\x00" + bytes((44, 95, 138)) * width for _ in range(height))
    def chunk(name, value):
        return struct.pack(">I", len(value)) + name + value + struct.pack(">I", zlib.crc32(name + value) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def project_fixture(photo_root: Path | None = None):
    target_key_1 = "냉동기|1|0|0"
    target_key_2 = "냉동기|2|1|1"
    photos = []
    if photo_root:
        first = photo_root / "first.png"
        second = photo_root / "second.png"
        png = _sample_png()
        first.write_bytes(png)
        second.write_bytes(png)
        photos = [
            {"장비키": target_key_1, "점검항목": "1. 유지관리 점검표 확인", "저장경로": str(first), "설명": "첫 장비 사진"},
            {"장비키": target_key_2, "점검항목": "1. 다른 장비 항목", "저장경로": str(second), "설명": "다른 장비 사진"},
        ]
    return {
        "현장정보": {
            "현장명": "TEST 현장",
            "주소": "TEST 주소",
            "관리주체": "TEST 관리주체",
            "용도": "업무시설",
            "연면적": "1000 ㎡",
            "점검시작일": "2026-08-01",
            "점검종료일": "2026-08-02",
            "보고서작성일": "2026-08-03",
        },
        "장비대장": [
            {"equipment_id": "internal-equipment-one", "설비종류": "냉동기", "관리번호": "CH-01", "설치위치": "기계실", "주요사양": "TEST 사양"},
            {"equipment_id": "internal-equipment-two", "설비종류": "냉동기", "관리번호": "CH-02"},
        ],
        "점검대상선정": [
            {"equipment_id": "internal-equipment-one", "설비종류": "냉동기", "점검번호": "1", "장비대장행": 0},
            {"equipment_id": "internal-equipment-two", "설비종류": "냉동기", "점검번호": "2", "장비대장행": 1},
        ],
        "설비별점검결과": {
            target_key_1: [
                {"equipment_id": "internal-equipment-one", "번호": "1", "점검내용": "유지관리 점검표 확인", "점검방법": "서류 확인", "점검기준": "점검표 보유 여부", "측정확인값": "확인", "설계정격값": "원문 기준", "판정": "○ 합격", "기술적소견": "특이사항 없음."},
                {"equipment_id": "internal-equipment-one", "번호": "2", "점검내용": "기내압력 점검", "점검방법": "측정", "점검기준": "운전 중 압력 확인", "측정확인값": "7.2 mmHg", "설계정격값": "6~9 mmHg", "판정": "○ 합격", "기술적소견": "기준범위 이내."},
            ],
            target_key_2: [
                {"equipment_id": "internal-equipment-two", "번호": "1", "점검내용": "다른 장비 항목", "판정": "X 불합격", "기술적소견": "재점검 필요"},
            ],
        },
        "사진관리": photos,
    }


def project_with_item_counts(*item_counts: int):
    project = project_fixture()
    if not item_counts:
        project["점검대상선정"] = []
        project["설비별점검결과"] = {}
        project["장비대장"] = []
        project["사진관리"] = []
        return project
    targets = []
    equipment = []
    results = {}
    template = project["설비별점검결과"]["냉동기|1|0|0"][0]
    for target_index, item_count in enumerate(item_counts):
        number = target_index + 1
        equipment_id = f"internal-equipment-{number}"
        target_key = f"냉동기|{number}|{target_index}|{target_index}"
        equipment.append({
            "equipment_id": equipment_id,
            "설비종류": "냉동기",
            "관리번호": f"CH-{number:02d}",
            "설치위치": f"기계실 {number}",
            "주요사양": f"TEST 사양 {number}",
        })
        targets.append({
            "equipment_id": equipment_id,
            "설비종류": "냉동기",
            "점검번호": str(number),
            "장비대장행": target_index,
        })
        results[target_key] = [
            {
                **template,
                "equipment_id": equipment_id,
                "번호": str(item_index),
                "점검내용": f"CH-{number:02d} 점검항목 {item_index}",
                "점검방법": "확인",
                "점검기준": "TEST 기준",
                "측정확인값": f"측정값 {number}-{item_index}",
                "기술적소견": "정상",
            }
            for item_index in range(1, item_count + 1)
        ]
    project["장비대장"] = equipment
    project["점검대상선정"] = targets
    project["설비별점검결과"] = results
    project["사진관리"] = []
    return project


class FakeHwp:
    def __init__(self):
        self.opened_html = ""
        self.saved = []
        self.inserted_pages = 0
        self.HAction = self

    def Open(self, path, *_args):
        self.opened_html = Path(path).read_text(encoding="cp949")
        return True

    def SaveAs(self, path, format_name, _options):
        Path(path).write_bytes((format_name + "\n" + self.opened_html).encode("utf-8"))
        self.saved.append((path, format_name))
        return True

    def MovePos(self, *_args):
        return True

    def Run(self, action):
        return action == "BreakPage"

    def Insert(self, path, *_args):
        self.opened_html += Path(path).read_text(encoding="cp949")
        self.inserted_pages += 1
        return True

    def Clear(self, *_args):
        return True

    def Quit(self):
        return True


class ProductionReportTests(unittest.TestCase):
    def test_report_document_maps_first_real_target_and_items(self):
        view = prepare_production_report(project_fixture())
        self.assertEqual(view.site.site_name, "TEST 현장")
        self.assertEqual(len(view.result_rows), 2)
        self.assertEqual(view.first_target.management_no, "CH-01")
        self.assertEqual(len(view.first_target.items), 2)
        self.assertEqual(view.first_target.items[1].measured_value, "7.2 mmHg")
        self.assertEqual(view.first_target.items[1].technical_note, "기준범위 이내.")
        self.assertEqual(len(view.targets), 2)
        self.assertEqual(view.targets[1].management_no, "CH-02")
        self.assertEqual(len(view.targets[1].items), 1)

    def test_page_plan_for_zero_one_and_two_targets(self):
        empty_plan = plan_production_pages(prepare_production_report(project_with_item_counts()))
        self.assertEqual(empty_plan.total_page_count, 18)
        self.assertEqual(empty_plan.target_plans, ())

        one_plan = plan_production_pages(prepare_production_report(project_with_item_counts(15)))
        self.assertEqual(one_plan.total_page_count, 26)
        self.assertEqual(one_plan.target_plans[0].inspection_page_count, 3)
        self.assertEqual(one_plan.target_plans[0].detail_page_count, 5)

        two_plan = plan_production_pages(prepare_production_report(project_with_item_counts(2, 8)))
        self.assertEqual(two_plan.total_page_count, 25)
        self.assertEqual(
            [plan.inspection_page_count for plan in two_plan.target_plans], [1, 2]
        )
        self.assertEqual(
            [plan.detail_page_count for plan in two_plan.target_plans], [1, 3]
        )
        self.assertEqual(two_plan.target_plans[0].inspection_start_page, 19)
        self.assertEqual(two_plan.target_plans[1].inspection_start_page, 21)

    def test_renderer_outputs_every_target_without_item_mixing(self):
        project = project_with_item_counts(2, 8)
        view = prepare_production_report(project)
        for target in view.targets:
            assert_summary_detail_consistency(target.items)
            expected_prefix = target.management_no
            for item in target.items:
                self.assertTrue(item.item_name.startswith(expected_prefix))
        fake = FakeHwp()
        with tempfile.TemporaryDirectory() as directory:
            result = generate_production_hwp(
                project,
                Path(directory) / "all-targets.hwp",
                renderer=HwpProductionRenderer(lambda: fake),
            )
        self.assertEqual(result.page_count, 25)
        self.assertEqual(fake.inserted_pages, 24)
        self.assertIn("CH-01 점검항목 1", fake.opened_html)
        self.assertIn("CH-02 점검항목 8", fake.opened_html)
        self.assertEqual(fake.opened_html.count("측정값 1-1"), 2)
        self.assertEqual(fake.opened_html.count("측정값 2-8"), 2)

    def test_internal_identifiers_are_not_customer_values(self):
        view = prepare_production_report(project_fixture())
        text = customer_visible_text(view)
        self.assertNotIn("internal-equipment-one", text)
        for token in FORBIDDEN_CUSTOMER_TOKENS:
            self.assertNotIn(token.lower(), text.lower())
        validate_customer_visible_text(view)

    def test_photo_selection_does_not_mix_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            view = prepare_production_report(project_fixture(Path(directory)))
            photos = view.first_target.items[0].photos
            self.assertEqual(len(photos), 1)
            self.assertEqual(photos[0].caption, "첫 장비 사진")
            self.assertNotIn("second.png", photos[0].file_path)
            second_photos = view.targets[1].items[0].photos
            self.assertEqual(len(second_photos), 1)
            self.assertEqual(second_photos[0].caption, "다른 장비 사진")
            self.assertNotIn("first.png", second_photos[0].file_path)

    def test_fifteen_items_drive_page_plan_without_summary_detail_split(self):
        project = project_with_item_counts(15, 1)
        fake = FakeHwp()
        renderer = HwpProductionRenderer(lambda: fake)
        with tempfile.TemporaryDirectory() as directory:
            result = generate_production_hwp(
                project, Path(directory) / "fifteen.hwp", renderer=renderer
            )
        self.assertEqual(result.page_count, 28)
        self.assertEqual(fake.inserted_pages, 27)

    def test_fake_hwp_generation_and_pdf_preview(self):
        fake = FakeHwp()
        renderer = HwpProductionRenderer(lambda: fake)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hwp = root / "production.hwp"
            pdf = root / "preview.pdf"
            result = generate_production_hwp(
                project_fixture(), hwp,
                renderer=renderer,
                pdf_preview_path=pdf,
            )
            self.assertTrue(hwp.is_file() and hwp.stat().st_size > 0)
            self.assertTrue(pdf.is_file() and pdf.stat().st_size > 0)
            self.assertGreaterEqual(result.page_count, 20)
            self.assertEqual(fake.inserted_pages, result.page_count - 1)
            self.assertIn("TEST 현장", fake.opened_html)
            self.assertIn("CH-01", fake.opened_html)
            self.assertIn("CH-02", fake.opened_html)
            self.assertNotIn("internal-equipment-one", fake.opened_html)
            for token in FORBIDDEN_CUSTOMER_TOKENS:
                self.assertNotIn(token, fake.opened_html)

    @unittest.skipUnless(os.environ.get("RUN_HWP_COM_TEST") == "1", "실제 HWP COM smoke test는 명시 실행")
    def test_actual_hwp_com_smoke(self):
        output = Path(os.environ["HWP_SMOKE_OUTPUT"])
        preview_value = os.environ.get("HWP_SMOKE_PDF", "")
        result = generate_production_hwp(
            project_fixture(output.parent), output,
            pdf_preview_path=Path(preview_value) if preview_value else None,
        )
        self.assertTrue(output.is_file() and output.stat().st_size > 0)
        expected = plan_production_pages(
            prepare_production_report(project_fixture(output.parent))
        ).total_page_count
        self.assertEqual(result.page_count, expected)
        if preview_value:
            preview = Path(preview_value)
            self.assertTrue(preview.is_file() and preview.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
