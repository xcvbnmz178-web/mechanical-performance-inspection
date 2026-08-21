import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from report import build_report_document, report_document_to_dict


class ReportServiceTests(unittest.TestCase):
    def test_workspace_projects_are_read_only_and_deterministic(self):
        projects = [
            {"현장정보": {"현장명": "테스트 현장 A"}},
            {"현장정보": {"현장명": "테스트 현장 B"}},
        ]
        with tempfile.TemporaryDirectory() as directory:
            files = []
            for index, project in enumerate(projects):
                path = Path(directory) / f"sample-{index}.json"
                path.write_text(json.dumps(project, ensure_ascii=False), encoding="utf-8")
                files.append(path)
            before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            for path in files:
                project = json.loads(path.read_text(encoding="utf-8"))
                original = copy.deepcopy(project)
                first = report_document_to_dict(build_report_document(project))
                second = report_document_to_dict(build_report_document(project))
                self.assertEqual(project, original)
                self.assertEqual(first, second)
                self.assertTrue(first["site"]["values"])
            after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
            self.assertEqual(before, after)

    def test_current_and_legacy_data_mapping(self):
        project = {
            "현장정보": {"현장명": "테스트"},
            "참여기술자": [{"성명": "홍길동"}],
            "장비대장": [
                {"equipment_id": "id-1", "설비종류": "냉동기", "관리번호": "CH-01", "세부유형": "turbo"},
                {"equipment_id": "id-2", "설비종류": "냉동기", "관리번호": "CH-02"},
            ],
            "점검대상선정": [
                {"equipment_id": "id-1", "설비종류": "냉동기", "점검번호": "1", "장비대장행": 0},
                {"equipment_id": "id-2", "설비종류": "냉동기", "점검번호": "1", "장비대장행": 1},
            ],
            "설비별점검결과": {
                "냉동기|1|0|0": [{"번호": "15", "점검내용": "COP 상태", "판정": "○ 합격", "criteria_results": [{"criterion_index": 0, "criterion_name": "측정 COP", "performed_methods": ["measurement"], "inspection_status": "checked", "criterion_judgment": "pass", "substitution": {}, "evidence_note": "계측"}]}],
                "냉동기|1|1|1": [{"번호": "15", "점검내용": "COP 상태", "판정": "미점검", "criteria_results": [{"criterion_index": 0, "criterion_name": "측정 COP", "performed_methods": [], "inspection_status": "unavailable", "criterion_judgment": "unset", "unavailable_reason": "equipment_stopped", "substitution": {"used": True, "method": "existing_data", "basis": "BMS"}, "evidence_note": ""}]}],
            },
            "사진관리": [
                {"장비키": "냉동기|1|0|0", "점검번호": "1", "점검항목": "15. COP 상태", "저장경로": "", "사진구분": "측정사진"},
                {"장비키": "냉동기|1|0|0", "점검번호": "1", "점검항목": "명판사진", "저장경로": "", "사진구분": "명판사진"},
            ],
            "성능계산": [{"equipment_id": "id-1", "종류": "터보냉동기", "입력값": {"a": 1}, "산출결과": [{"값": "5.82"}], "핵심지표": "COP", "핵심값": "5.82", "판정": "참고", "관리번호_snapshot": "CH-01"}],
            "에너지분석": {"에너지사용량": [{"연도": "2025"}], "결과요약": "현장 전체"},
            "시스템검토": {"시스템작동상태": [{"설비명": "냉동기", "판정": "확인필요", "비고": "사용자값"}]},
            "전년도비교": {"비교결과": [{"구분": "에너지"}]},
            "원인분석": [{"장비키": "냉동기|1|0|0", "최종원인": "원인"}],
            "성능개선계획": {"부적합개선사항": [{"대상설비": "냉동기"}], "5개년개선계획": [{"연도": "2027"}]},
        }
        original = copy.deepcopy(project)
        document = build_report_document(project)
        self.assertEqual(project, original)
        self.assertEqual([target.equipment_id for target in document.targets], ["id-1", "id-2"])
        self.assertNotEqual(document.targets[0].target_key, document.targets[1].target_key)
        self.assertEqual(document.targets[0].inspection_items[0].criteria_results[0].inspection_status, "checked")
        self.assertEqual(document.targets[1].inspection_items[0].criteria_results[0].inspection_status, "unavailable")
        self.assertEqual(len(document.targets[0].photos), 2)
        self.assertEqual(len(document.targets[0].inspection_items[0].photos), 1)
        self.assertEqual(document.performance_calculations[0].equipment_id, "id-1")
        self.assertEqual(document.energy_analysis.yearly_records, [{"연도": "2025"}])
        self.assertFalse(hasattr(document.energy_analysis, "equipment_id"))
        self.assertEqual(document.system_reviews[0].judgment, "확인필요")
        self.assertEqual(document.root_cause_analysis[0].values["최종원인"], "원인")
        self.assertEqual(len(document.improvement_plans), 2)

        legacy = copy.deepcopy(project)
        del legacy["설비별점검결과"]["냉동기|1|0|0"][0]["criteria_results"]
        legacy_document = build_report_document(legacy)
        self.assertEqual(legacy_document.targets[0].inspection_items[0].criteria_results, [])


if __name__ == "__main__":
    unittest.main()
