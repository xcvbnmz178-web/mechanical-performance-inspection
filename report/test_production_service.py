import os
from pathlib import Path
import struct
import tempfile
import unittest
import zlib

from report.hwp_production_renderer import (
    HwpProductionRenderer,
    HwpSecurityModuleRegistrationError,
)
from report.production_model import ProductionCompanyView
from report.production_page_plan import plan_production_pages
from report.production_service import (
    ProductionPhotoFileMissingError,
    ProductionProjectDataError,
    ProductionSecurityModuleMissingError,
    generate_production_hwp,
    prepare_production_report,
    validate_production_document,
    verify_production_hwp_environment,
)
from report.service import build_report_document
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


def phase3_project_fixture():
    project = project_with_item_counts(2, 1)
    project["시스템검토"] = {
        "검토사항총괄": [
            {
                "점검항목": f"검토항목 {index}",
                "세부검토사항": f"세부사항 {index}",
                "고정검토기준": f"검토기준 {index}",
                "결과요약": "검토완료",
            }
            for index in range(1, 5)
        ],
        "유지관리지침서": [
            {
                "구비서류": f"구비서류 {index}",
                "보유상태": "유",
                "책임기술자소견": "확인",
                "비고": "",
            }
            for index in range(1, 8)
        ],
        "시스템작동상태": [
            {
                "구분": "열원설비",
                "대상설비": f"냉동기 CH-{index:02d}",
                "점검결과": "○",
                "비고": "정상",
            }
            for index in range(1, 5)
        ],
        "설계측정값일치": [
            {
                "구분": "열원설비",
                "대상설비": f"냉동기 CH-{index:02d}",
                "점검결과": "○",
                "비교근거": "설계값과 측정값 비교",
                "비고": "정상",
            }
            for index in range(1, 3)
        ],
    }
    project["노후도분석"] = {
        "노후도표": [
            {
                "구분": "열원설비",
                "대상설비": "냉동기",
                "장비번호계통명": f"CH-{index:02d}",
                "설치연도": "2025",
                "참고내용연수": "12",
                "사용연수": "1",
                "노후도": "정상",
                "적용근거": "TEST 내용연수표",
                "비고": "",
            }
            for index in range(1, 3)
        ],
        "내용연수적용근거": "TEST 내용연수표",
        "종합의견": "저장된 노후도 자료 기준 정상",
    }
    project["성능개선계획"] = {
        "부적합개선사항": [
            {
                "구분": "열원설비",
                "대상설비": "냉동기",
                "장비번호계통명": f"CH-{index:02d}",
                "부적합사항": f"CH-{index:02d} 확인사항",
                "개선사항": f"CH-{index:02d} 개선조치",
            }
            for index in range(1, 3)
        ],
        "5개년개선계획": [
            {
                "구분": "열원설비",
                "대상설비": "냉동기",
                "장비번호계통명": f"CH-{index:02d}",
                "성능개선 필요성": f"CH-{index:02d} 예방정비",
                "1년차": "점검",
                "2년차": "-",
                "3년차": "정비",
                "4년차": "-",
                "5년차": "-",
            }
            for index in range(1, 3)
        ],
    }
    return project


class FakeHwp:
    def __init__(self):
        self.opened_html = ""
        self.saved = []
        self.inserted_pages = 0
        self.HAction = self

    def RegisterModule(self, *_args):
        return True

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
        self.assertEqual(empty_plan.total_page_count, 23)
        self.assertEqual(empty_plan.target_plans, ())

        one_plan = plan_production_pages(prepare_production_report(project_with_item_counts(15)))
        self.assertEqual(one_plan.total_page_count, 31)
        self.assertEqual(one_plan.target_plans[0].inspection_page_count, 3)
        self.assertEqual(one_plan.target_plans[0].detail_page_count, 5)

        two_plan = plan_production_pages(prepare_production_report(project_with_item_counts(2, 8)))
        self.assertEqual(two_plan.total_page_count, 30)
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
        self.assertEqual(result.page_count, 30)
        self.assertEqual(fake.inserted_pages, 29)
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
            self.assertEqual(view.first_target.overview_photo.caption, "첫 장비 사진")
            self.assertNotIn("second.png", view.first_target.overview_photo.file_path)
            self.assertEqual(view.targets[1].overview_photo.caption, "다른 장비 사진")
            self.assertNotIn("first.png", view.targets[1].overview_photo.file_path)

    def test_overview_photo_is_not_repeated_in_item_photos(self):
        with tempfile.TemporaryDirectory() as directory:
            view = prepare_production_report(project_fixture(Path(directory)))
            self.assertTrue(view.first_target.overview_photo)
            self.assertEqual(view.first_target.items[0].photos, ())

    def test_distinct_overview_and_item_photos_are_both_kept(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overview = root / "overview.png"
            detail = root / "detail.png"
            overview.write_bytes(_sample_png())
            detail.write_bytes(_sample_png())
            project = project_fixture()
            project["사진관리"] = [
                {"장비키": "냉동기|1|0|0", "사진구분": "equipment_overview", "저장경로": str(overview)},
                {"장비키": "냉동기|1|0|0", "점검항목": "1. 유지관리 점검표 확인", "저장경로": str(detail)},
            ]
            view = prepare_production_report(project)
            self.assertEqual(Path(view.first_target.overview_photo.file_path), overview)
            self.assertEqual(tuple(Path(p.file_path) for p in view.first_target.items[0].photos), (detail,))

    def test_two_distinct_item_photos_are_kept_after_overview(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / f"photo-{index}.png" for index in range(3)]
            for path in paths:
                path.write_bytes(_sample_png())
            project = project_fixture()
            project["사진관리"] = [
                {"장비키": "냉동기|1|0|0", "사진구분": "equipment_overview", "저장경로": str(paths[0])},
                {"장비키": "냉동기|1|0|0", "점검항목": "1. 유지관리 점검표 확인", "저장경로": str(paths[1])},
                {"장비키": "냉동기|1|0|0", "점검항목": "1. 유지관리 점검표 확인", "저장경로": str(paths[2])},
            ]
            view = prepare_production_report(project)
            self.assertEqual(tuple(Path(p.file_path) for p in view.first_target.items[0].photos), tuple(paths[1:]))

    def test_duplicate_item_path_is_kept_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            overview = root / "overview.png"
            detail = root / "detail.png"
            overview.write_bytes(_sample_png())
            detail.write_bytes(_sample_png())
            project = project_fixture()
            project["사진관리"] = [
                {"장비키": "냉동기|1|0|0", "사진구분": "equipment_overview", "저장경로": str(overview)},
                {"장비키": "냉동기|1|0|0", "점검항목": "1. 유지관리 점검표 확인", "저장경로": str(detail)},
                {"장비키": "냉동기|1|0|0", "점검항목": "1. 유지관리 점검표 확인", "저장경로": str(detail)},
            ]
            view = prepare_production_report(project)
            self.assertEqual(len(view.first_target.items[0].photos), 1)

    def test_same_path_is_allowed_once_per_target(self):
        with tempfile.TemporaryDirectory() as directory:
            shared = Path(directory) / "shared.png"
            shared.write_bytes(_sample_png())
            project = project_fixture()
            project["사진관리"] = [
                {"장비키": "냉동기|1|0|0", "저장경로": str(shared)},
                {"장비키": "냉동기|2|1|1", "저장경로": str(shared)},
            ]
            view = prepare_production_report(project)
            self.assertEqual(Path(view.targets[0].overview_photo.file_path), shared)
            self.assertEqual(Path(view.targets[1].overview_photo.file_path), shared)

    def test_target_without_photos_remains_empty(self):
        view = prepare_production_report(project_fixture())
        self.assertIsNone(view.targets[0].overview_photo)
        self.assertTrue(all(not item.photos for item in view.targets[0].items))

    def test_phase3_views_and_page_plan_use_saved_data(self):
        view = prepare_production_report(phase3_project_fixture())
        self.assertEqual(len(view.system_review.summary_rows), 4)
        self.assertEqual(len(view.system_review.document_rows), 7)
        self.assertEqual(len(view.system_review.operation_rows), 6)
        self.assertEqual(view.system_review.status, "검토완료")
        self.assertEqual(len(view.aging.rows), 2)
        self.assertEqual(view.aging.rows[0].management_no, "CH-01")
        self.assertEqual(view.aging.rows[0].reference_lifespan, "12")
        self.assertEqual(len(view.improvements.rows), 4)
        first_rows = [row for row in view.improvements.rows if "CH-01" in row.target_label]
        second_rows = [row for row in view.improvements.rows if "CH-02" in row.target_label]
        self.assertEqual(len(first_rows), 2)
        self.assertEqual(len(second_rows), 2)
        self.assertTrue(all("CH-02" not in row.action for row in first_rows))
        self.assertTrue(all("CH-01" not in row.action for row in second_rows))

        plan = plan_production_pages(view)
        self.assertEqual(plan.system_review_summary_page_count, 2)
        self.assertEqual(plan.document_review_page_count, 2)
        self.assertEqual(plan.operation_review_page_count, 2)
        self.assertEqual(plan.aging_page_count, 1)
        self.assertEqual(plan.improvement_page_count, 2)
        self.assertEqual(plan.total_page_count, 31)
        validate_customer_visible_text(view)

    def test_phase3_renderer_outputs_all_sections(self):
        project = phase3_project_fixture()
        fake = FakeHwp()
        with tempfile.TemporaryDirectory() as directory:
            result = generate_production_hwp(
                project,
                Path(directory) / "phase3.hwp",
                renderer=HwpProductionRenderer(lambda: fake),
            )
        self.assertEqual(result.page_count, 31)
        self.assertEqual(fake.inserted_pages, 30)
        self.assertIn("시스템검토 요약", fake.opened_html)
        self.assertIn("자료보유 및 확인사항", fake.opened_html)
        self.assertIn("작동상태 및 운전검토", fake.opened_html)
        self.assertIn("노후도 분석", fake.opened_html)
        self.assertIn("CH-01 개선조치", fake.opened_html)
        self.assertIn("CH-02 개선조치", fake.opened_html)
        self.assertNotIn("internal-equipment", fake.opened_html)

    def test_phase3_missing_data_stays_explicitly_empty(self):
        view = prepare_production_report(project_with_item_counts(1))
        self.assertEqual(view.system_review.status, "자료없음")
        self.assertEqual(view.system_review.summary_rows, ())
        self.assertEqual(view.aging.status, "자료없음")
        self.assertEqual(view.aging.rows, ())
        self.assertEqual(view.improvements.status, "자료없음")
        self.assertEqual(view.improvements.rows, ())
        plan = plan_production_pages(view)
        self.assertEqual(plan.system_review_summary_page_count, 1)
        self.assertEqual(plan.document_review_page_count, 1)
        self.assertEqual(plan.operation_review_page_count, 1)
        self.assertEqual(plan.aging_page_count, 1)
        self.assertEqual(plan.improvement_page_count, 1)

    def test_rca_improvement_fallback_is_target_specific(self):
        project = project_with_item_counts(1, 1)
        project["원인분석"] = [{
            "대상설비": "냉동기 | CH-02",
            "점검항목": "CH-02 점검항목 1",
            "이상현상": "CH-02 이상",
            "개선방안": "CH-02 전용 개선",
        }]
        view = prepare_production_report(project)
        self.assertEqual(len(view.improvements.rows), 1)
        row = view.improvements.rows[0]
        self.assertIn("CH-02", row.target_label)
        self.assertNotIn("CH-01", row.target_label)
        self.assertEqual(row.action, "CH-02 전용 개선")

    def test_ambiguous_improvement_does_not_attach_to_same_type_target(self):
        project = project_with_item_counts(1, 1)
        project["성능개선계획"] = {
            "부적합개선사항": [{
                "대상설비": "냉동기",
                "부적합사항": "공통 확인사항",
                "개선사항": "대상 확인 후 조치",
            }]
        }
        view = prepare_production_report(project)
        self.assertEqual(len(view.improvements.rows), 1)
        self.assertEqual(
            view.improvements.rows[0].target_label,
            "냉동기 (대상 확인필요)",
        )
        self.assertEqual(view.improvements.status, "확인필요")

    def test_fifteen_items_drive_page_plan_without_summary_detail_split(self):
        project = project_with_item_counts(15, 1)
        fake = FakeHwp()
        renderer = HwpProductionRenderer(lambda: fake)
        with tempfile.TemporaryDirectory() as directory:
            result = generate_production_hwp(
                project, Path(directory) / "fifteen.hwp", renderer=renderer
            )
        self.assertEqual(result.page_count, 33)
        self.assertEqual(fake.inserted_pages, 32)

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

    def test_production_environment_reports_missing_official_dll(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "FilePathCheckerModuleExample.dll"
            with self.assertRaises(ProductionSecurityModuleMissingError):
                verify_production_hwp_environment(missing)

    def test_production_environment_requires_true_registration_and_quits(self):
        class SecurityHwp:
            def __init__(self, registered):
                self.registered = registered
                self.cleared = False
                self.quit_called = False

            def RegisterModule(self, kind, name):
                self.args = (kind, name)
                return self.registered

            def Clear(self, *_args):
                self.cleared = True

            def Quit(self):
                self.quit_called = True

        with tempfile.TemporaryDirectory() as directory:
            dll = Path(directory) / "FilePathCheckerModuleExample.dll"
            dll.write_bytes(b"MZ")
            failed = SecurityHwp(False)
            with self.assertRaises(HwpSecurityModuleRegistrationError):
                verify_production_hwp_environment(dll, com_factory=lambda: failed)
            self.assertTrue(failed.cleared)
            self.assertTrue(failed.quit_called)

            passed = SecurityHwp(True)
            verify_production_hwp_environment(dll, com_factory=lambda: passed)
            self.assertEqual(
                passed.args,
                ("FilePathCheckDLL", "FilePathCheckerModuleExample"),
            )
            self.assertTrue(passed.cleared)
            self.assertTrue(passed.quit_called)

    def test_production_document_requires_target_results(self):
        empty = build_report_document(project_with_item_counts())
        with self.assertRaises(ProductionProjectDataError):
            validate_production_document(empty)
        validate_production_document(
            build_report_document(project_with_item_counts(1))
        )

    def test_production_document_rejects_missing_photo_file(self):
        project = project_with_item_counts(1)
        project["사진관리"] = [{
            "장비키": "냉동기|1|0|0",
            "점검항목": "1. CH-01 점검항목 1",
            "저장경로": str(Path("missing-production-photo.png").resolve()),
        }]
        document = build_report_document(project)
        with self.assertRaises(ProductionPhotoFileMissingError):
            validate_production_document(document)

    def test_renderer_requires_true_security_registration(self):
        class RejectedHwp(FakeHwp):
            def RegisterModule(self, *_args):
                return False

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(HwpSecurityModuleRegistrationError):
                generate_production_hwp(
                    phase3_project_fixture(),
                    Path(directory) / "rejected.hwp",
                    renderer=HwpProductionRenderer(lambda: RejectedHwp()),
                )

    def test_generation_progress_reports_hwp_and_pdf_stages(self):
        stages = []
        with tempfile.TemporaryDirectory() as directory:
            generate_production_hwp(
                phase3_project_fixture(),
                Path(directory) / "progress.hwp",
                pdf_preview_path=Path(directory) / "progress.pdf",
                renderer=HwpProductionRenderer(lambda: FakeHwp()),
                progress_callback=stages.append,
            )
        self.assertEqual(stages, ["HWP 생성 중", "PDF 비교본 생성 중"])

    @unittest.skipUnless(os.environ.get("RUN_HWP_COM_TEST") == "1", "실제 HWP COM smoke test는 명시 실행")
    def test_actual_hwp_com_smoke(self):
        output = Path(os.environ["HWP_SMOKE_OUTPUT"])
        preview_value = os.environ.get("HWP_SMOKE_PDF", "")
        project = phase3_project_fixture()
        result = generate_production_hwp(
            project, output,
            pdf_preview_path=Path(preview_value) if preview_value else None,
        )
        self.assertTrue(output.is_file() and output.stat().st_size > 0)
        expected = plan_production_pages(
            prepare_production_report(project)
        ).total_page_count
        self.assertEqual(result.page_count, expected)
        if preview_value:
            preview = Path(preview_value)
            self.assertTrue(preview.is_file() and preview.stat().st_size > 0)


if __name__ == "__main__":
    unittest.main()
