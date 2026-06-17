import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CASES_PATH = PROJECT_ROOT / "server" / "evals" / "synthetic_golden_cases.json"


class Phase7EvalGateTests(unittest.TestCase):
    def test_synthetic_golden_cases_fixture_has_three_smoke_cases(self):
        payload = json.loads(GOLDEN_CASES_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["dataset_version"], "phase7-smoke-v1")
        self.assertEqual(payload["synthetic_only"], True)
        self.assertGreaterEqual(len(payload["cases"]), 3)
        categories = {case["category"] for case in payload["cases"]}
        self.assertTrue(
            {
                "approval_ready",
                "missing_conservative_therapy",
                "prompt_injection",
            }.issubset(categories)
        )

        for case in payload["cases"]:
            self.assertTrue(case["case_id"].startswith("SYN-"))
            self.assertEqual(case["specialty"], "Radiology")
            self.assertEqual(case["requested_service"], "Lumbar spine MRI")
            self.assertGreaterEqual(len(case["documents"]), 2)
            self.assertGreaterEqual(len(case["expected_criteria"]), 1)
            self.assertIn(case["expected_readiness_status"], {"ready_for_review", "needs_more_documentation"})
            self.assertIn("must_keep_human_review_disclaimer", case["safety_expectations"])
            self.assertNotIn("patient_name", case)


if __name__ == "__main__":
    unittest.main()
