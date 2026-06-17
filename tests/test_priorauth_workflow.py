import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class PriorAuthWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        self.server_dir = self.project_root / "server"
        self.original_cwd = Path.cwd()
        self.original_path = list(sys.path)
        self.tmpdir = tempfile.TemporaryDirectory()
        os.chdir(self.server_dir)
        sys.path.insert(0, str(self.server_dir))
        self._clear_server_modules()
        self.env_patch = {
            "DATABASE_URL": f"sqlite:///{Path(self.tmpdir.name) / 'authlens-test.db'}",
            "JWT_SECRET": "test-secret",
            "ENVIRONMENT": "test",
        }
        self._original_env = {key: os.environ.get(key) for key in self.env_patch}
        os.environ.update(self.env_patch)

    def tearDown(self):
        session = sys.modules.get("db.session")
        if session is not None:
            session.dispose_engine()
        self._clear_server_modules()
        for key, value in self._original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        sys.path[:] = self.original_path
        os.chdir(self.original_cwd)
        self.tmpdir.cleanup()

    def _clear_server_modules(self):
        prefixes = (
            "db",
            "dependencies",
            "models",
            "routes.auth",
            "routes.cases",
            "routes.documents",
            "routes.criteria",
            "routes.evidence",
            "routes.reports",
            "routes.drafts",
            "services",
        )
        for module_name in list(sys.modules):
            if module_name == "main" or module_name.startswith(prefixes):
                sys.modules.pop(module_name, None)

    def _client(self):
        main = importlib.import_module("main")
        session = importlib.import_module("db.session")
        seed_demo = importlib.import_module("db.seed_demo")
        session.init_db()
        seed_demo.seed_demo_data()
        return TestClient(main.app)

    def _login(self, client, email="coordinator@demo.authlens.test", password="demo-password"):
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def test_seeded_demo_user_can_login_and_read_profile(self):
        client = self._client()

        token = self._login(client)
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "coordinator@demo.authlens.test")
        self.assertEqual(response.json()["role"], "coordinator")
        self.assertEqual(response.json()["organization"]["name"], "Demo Spine Clinic")

    def test_coordinator_can_create_and_list_org_scoped_cases(self):
        client = self._client()
        token = self._login(client)

        create_response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "patient_label": "SYN-LMRI-001",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "service_code": "72148",
                "case_type": "prior_auth",
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.text)
        case_payload = create_response.json()
        self.assertEqual(case_payload["status"], "draft")
        self.assertEqual(case_payload["readiness_score"], None)

        list_response = client.get(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(list_response.status_code, 200)
        cases = list_response.json()["cases"]
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["id"], case_payload["id"])
        self.assertEqual(cases[0]["missing_required_criteria_count"], 0)

    def test_viewer_cannot_create_cases(self):
        client = self._client()
        token = self._login(client, email="viewer@demo.authlens.test")

        response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "patient_label": "SYN-LMRI-002",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "prior_auth",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Insufficient role"})

    def test_case_documents_preserve_type_and_tenant_metadata(self):
        client = self._client()
        token = self._login(client)
        case_response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "patient_label": "SYN-LMRI-003",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "prior_auth",
            },
        )
        case_id = case_response.json()["id"]

        response = client.post(
            f"/api/cases/{case_id}/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={"document_type": "payer_policy"},
            files={"file": ("policy.pdf", b"%PDF-1.4\npolicy text", "application/pdf")},
        )

        self.assertEqual(response.status_code, 201, response.text)
        payload = response.json()
        self.assertEqual(payload["case_id"], case_id)
        self.assertEqual(payload["document_type"], "payer_policy")
        self.assertEqual(payload["processing_status"], "indexed")
        self.assertEqual(payload["page_count"], 1)

    def test_priorauth_analysis_generates_evidence_report_draft_and_citation_check(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@demo.authlens.test")
        case_response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={
                "patient_label": "SYN-LMRI-004",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "prior_auth",
            },
        )
        case_id = case_response.json()["id"]
        for document_type, name, body in [
            (
                "payer_policy",
                "policy.pdf",
                b"%PDF-1.4\nCoverage requires six weeks of conservative therapy. Functional limitation must be documented.",
            ),
            (
                "patient_note",
                "note.pdf",
                b"%PDF-1.4\nThe provided documents indicate six weeks of conservative therapy and functional limitation with walking.",
            ),
        ]:
            response = client.post(
                f"/api/cases/{case_id}/documents",
                headers={"Authorization": f"Bearer {coordinator_token}"},
                data={"document_type": document_type},
                files={"file": (name, body, "application/pdf")},
            )
            self.assertEqual(response.status_code, 201, response.text)

        criteria_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(criteria_response.status_code, 200, criteria_response.text)
        criteria = criteria_response.json()["criteria"]
        self.assertGreaterEqual(len(criteria), 2)
        self.assertTrue(all(item["source_file"] == "policy.pdf" for item in criteria))

        evidence_response = client.post(
            f"/api/cases/{case_id}/evidence/match",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(evidence_response.status_code, 200, evidence_response.text)
        matches = evidence_response.json()["matches"]
        self.assertEqual(len(matches), len(criteria))
        self.assertIn("met", {match["status"] for match in matches})
        for match in matches:
            if match["status"] == "met":
                self.assertEqual(match["source_file"], "note.pdf")
                self.assertTrue(match["source_quote"])

        report_response = client.post(
            f"/api/cases/{case_id}/reports/readiness",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        report = report_response.json()
        self.assertGreater(report["readiness_score"], 0)
        self.assertIn("documentation completeness", report["summary"])

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/prior-auth",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        draft = draft_response.json()
        self.assertIn("Clinician review is required", draft["content_markdown"])
        self.assertNotIn("guaranteed", draft["content_markdown"].lower())

        check_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(check_response.status_code, 200, check_response.text)
        self.assertEqual(check_response.json()["verification_status"], "pass")

        approve_response = client.post(
            f"/api/drafts/{draft['id']}/approve",
            headers={"Authorization": f"Bearer {clinician_token}"},
        )
        self.assertEqual(approve_response.status_code, 200, approve_response.text)
        self.assertEqual(approve_response.json()["status"], "approved")


if __name__ == "__main__":
    unittest.main()
