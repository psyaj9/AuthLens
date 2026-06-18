import json
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CASES_PATH = PROJECT_ROOT / "server" / "evals" / "synthetic_golden_cases.json"
SERVER_DIR = PROJECT_ROOT / "server"


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
            for document in case["documents"]:
                self.assertTrue(document["body"].startswith("%PDF-1.4"))

    def test_synthetic_smoke_eval_runner_executes_priorauth_workflow(self):
        sys.path.insert(0, str(SERVER_DIR))
        try:
            from evals.run_synthetic_eval import run_smoke_eval

            result = run_smoke_eval()
        finally:
            sys.path.remove(str(SERVER_DIR))

        self.assertEqual(result["dataset_version"], "phase7-smoke-v1")
        self.assertGreaterEqual(result["total_cases"], 3)
        self.assertEqual(result["failed_cases"], [])
        self.assertEqual(result["passed_cases"], result["total_cases"])
        for case_result in result["case_results"]:
            self.assertEqual(
                case_result["actual_readiness_status"],
                case_result["expected_readiness_status"],
            )
            self.assertTrue(case_result["safety_passed"])


if __name__ == "__main__":
    unittest.main()
