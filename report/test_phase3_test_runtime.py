import unittest

from report.phase3_test_runtime import build_current_project_snapshot


class FakeApp:
    inspection_results = {"target": [{"판정": "○ 합격"}]}
    previous_project_path = ""
    previous_compare_results = []
    performance_calculations = []

    def __getattr__(self, name):
        if name.startswith("collect_"):
            return lambda: []
        raise AttributeError(name)

    def collect_site_data(self):
        return {"현장명": "테스트 현장"}

    def collect_system_review_data(self):
        return {}

    def collect_energy_data(self):
        return {}


class Phase3RuntimeTests(unittest.TestCase):
    def test_snapshot_is_detached_from_live_inspection_results(self):
        app = FakeApp()
        snapshot = build_current_project_snapshot(app)
        snapshot["설비별점검결과"]["target"][0]["판정"] = "X 부적합"
        self.assertEqual(app.inspection_results["target"][0]["판정"], "○ 합격")

    def test_snapshot_uses_existing_project_keys(self):
        snapshot = build_current_project_snapshot(FakeApp())
        self.assertEqual(snapshot["현장정보"]["현장명"], "테스트 현장")
        self.assertIn("장비대장", snapshot)
        self.assertIn("점검대상선정", snapshot)
        self.assertIn("설비별점검결과", snapshot)


if __name__ == "__main__":
    unittest.main()
