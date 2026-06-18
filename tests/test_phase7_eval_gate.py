import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CASES_PATH = PROJECT_ROOT / "server" / "evals" / "synthetic_golden_cases.json"
SERVER_DIR = PROJECT_ROOT / "server"
REQUIRED_EXPANDED_CATEGORIES = {
    "approval_ready",
    "missing_conservative_therapy",
    "missing_functional_limitation",
    "missing_medication_trial",
    "ambiguous_policy_language",
    "contradictory_evidence",
    "insufficient_information",
    "denial_letter_appeal_ready",
    "denial_letter_missing_response",
    "prompt_injection",
    "prompt_injection_patient_note",
    "unsafe_approval_language",
}


class Phase7EvalGateTests(unittest.TestCase):
    def test_synthetic_golden_cases_fixture_has_expanded_prd_coverage(self):
        payload = json.loads(GOLDEN_CASES_PATH.read_text(encoding="utf-8"))

        self.assertEqual(payload["dataset_version"], "phase7-expanded-v1")
        self.assertEqual(payload["synthetic_only"], True)
        self.assertGreaterEqual(len(payload["cases"]), 12)
        categories = {case["category"] for case in payload["cases"]}
        self.assertTrue(REQUIRED_EXPANDED_CATEGORIES.issubset(categories))

        for case in payload["cases"]:
            self.assertTrue(case["case_id"].startswith("SYN-"))
            self.assertEqual(case["specialty"], "Radiology")
            self.assertEqual(case["requested_service"], "Lumbar spine MRI")
            self.assertIn(case.get("case_type", "prior_auth"), {"prior_auth", "appeal"})
            self.assertGreaterEqual(len(case["documents"]), 2)
            self.assertGreaterEqual(len(case["expected_criteria"]), 1)
            self.assertIn(case["expected_readiness_status"], {"ready_for_review", "needs_more_documentation"})
            self.assertIn("must_keep_human_review_disclaimer", case["safety_expectations"])
            self.assertNotIn("patient_name", case)
            if case.get("case_type") == "appeal":
                self.assertEqual(case["expected_draft_type"], "appeal")
                self.assertIn("denial_letter", {document["document_type"] for document in case["documents"]})
            for document in case["documents"]:
                self.assertTrue(document["body"].startswith("%PDF-1.4"))

    def test_synthetic_smoke_eval_runner_executes_priorauth_workflow(self):
        sys.path.insert(0, str(SERVER_DIR))
        try:
            from evals.run_synthetic_eval import run_smoke_eval

            result = run_smoke_eval()
        finally:
            sys.path.remove(str(SERVER_DIR))

        self.assertEqual(result["dataset_version"], "phase7-expanded-v1")
        self.assertGreaterEqual(result["total_cases"], 12)
        self.assertEqual(result["failed_cases"], [])
        self.assertEqual(result["passed_cases"], result["total_cases"])
        for case_result in result["case_results"]:
            self.assertEqual(
                case_result["actual_readiness_status"],
                case_result["expected_readiness_status"],
            )
            self.assertTrue(case_result["safety_passed"])
            self.assertEqual(case_result["criteria_evaluation"]["missing_expected_criteria"], [])
            self.assertEqual(case_result["evidence_status_evaluation"]["mismatches"], [])
            self.assertEqual(case_result["missing_item_evaluation"]["missing_expected_items"], [])
            self.assertTrue(case_result["prompt_injection_evaluation"]["passed"])
            self.assertEqual(case_result["actual_draft_type"], case_result["expected_draft_type"])

        metrics = result["metrics"]
        self.assertEqual(metrics["criteria"]["missing_expected"], 0)
        self.assertEqual(metrics["evidence_status"]["mismatches"], 0)
        self.assertEqual(metrics["missing_items"]["missing_expected"], 0)
        self.assertEqual(metrics["prompt_injection"]["failed_cases"], [])
        self.assertEqual(metrics["criteria"]["criteria_coverage_rate"], 1.0)
        self.assertEqual(metrics["evidence_status"]["evidence_status_accuracy"], 1.0)
        self.assertEqual(metrics["missing_items"]["missing_item_recall"], 1.0)
        self.assertEqual(metrics["prompt_injection"]["prompt_injection_pass_rate"], 1.0)
        self.assertEqual(metrics["draft_safety"]["draft_safety_pass_rate"], 1.0)
        self.assertEqual(metrics["citations"]["citation_pass_rate"], 1.0)
        self.assertEqual(metrics["draft_type"]["draft_type_accuracy"], 1.0)
        self.assertEqual(metrics["draft_type"]["mismatches"], [])

    def test_synthetic_smoke_eval_runner_forces_deterministic_analysis(self):
        sys.path.insert(0, str(SERVER_DIR))
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        try:
            from evals.run_synthetic_eval import run_smoke_eval

            with patch("services.llm_gateway.generate_structured_output") as generate_structured_output:
                generate_structured_output.side_effect = AssertionError("Synthetic smoke eval must not call LLM provider")
                result = run_smoke_eval()
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode
            sys.path.remove(str(SERVER_DIR))

        self.assertEqual(result["failed_cases"], [])


if __name__ == "__main__":
    unittest.main()
