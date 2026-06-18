import json
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
            "routes.audit",
            "services",
        )
        for module_name in list(sys.modules):
            if module_name == "main" or module_name.startswith(prefixes):
                sys.modules.pop(module_name, None)

    def _client(self):
        main = importlib.import_module("main")
        session = importlib.import_module("db.session")
        session.init_db()
        return TestClient(main.app)

    def _role_for_email(self, email):
        if email.startswith("admin"):
            return "admin"
        if email.startswith("clinician"):
            return "clinician_reviewer"
        if email.startswith("viewer"):
            return "viewer"
        return "coordinator"

    def _create_test_user(
        self,
        email="coordinator@test.authlens.local",
        password="test-password",
        role=None,
        name="Test User",
        organization_id="org_test_spine",
        organization_name="Test Spine Clinic",
    ):
        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        auth = importlib.import_module("modules.auth")
        selected_role = role or self._role_for_email(email)
        with session.SessionLocal() as db:
            org = db.get(models.Organization, organization_id)
            if org is None:
                org = models.Organization(id=organization_id, name=organization_name, plan="test")
                db.add(org)
            user = db.scalar(importlib.import_module("sqlalchemy").select(models.User).where(models.User.email == email))
            if user is None:
                user = models.User(
                    email=email,
                    name=name,
                    password_hash=auth.hash_password(password),
                    is_active=True,
                )
                db.add(user)
                db.flush()
            membership = db.scalar(
                importlib.import_module("sqlalchemy").select(models.OrganizationMembership).where(
                    models.OrganizationMembership.user_id == user.id,
                    models.OrganizationMembership.organization_id == org.id,
                )
            )
            if membership is None:
                db.add(
                    models.OrganizationMembership(
                        user_id=user.id,
                        organization_id=org.id,
                        role=selected_role,
                    )
                )
            else:
                membership.role = selected_role
            db.commit()
            return user.id

    def _login(self, client, email="coordinator@test.authlens.local", password="test-password"):
        self._create_test_user(email=email, password=password)
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def _create_case(self, client, token, patient_label="SYN-LMRI-CASE"):
        response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "patient_label": patient_label,
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "prior_auth",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["id"]

    def _upload_document(self, client, token, case_id, document_type, filename, body):
        response = client.post(
            f"/api/cases/{case_id}/documents",
            headers={"Authorization": f"Bearer {token}"},
            data={"document_type": document_type},
            files={"file": (filename, body, "application/pdf")},
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def _prepare_case_with_policy_and_note(self, client, token):
        case_id = self._create_case(client, token, "SYN-LMRI-FLOW")
        self._upload_document(
            client,
            token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy. Functional limitation must be documented.",
        )
        self._upload_document(
            client,
            token,
            case_id,
            "patient_note",
            "note.pdf",
            b"%PDF-1.4\nThe provided documents indicate six weeks of conservative therapy and functional limitation with walking.",
        )
        criteria_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(criteria_response.status_code, 200, criteria_response.text)
        evidence_response = client.post(
            f"/api/cases/{case_id}/evidence/match",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(evidence_response.status_code, 200, evidence_response.text)
        report_response = client.post(
            f"/api/cases/{case_id}/reports/readiness",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        return case_id, criteria_response.json()["criteria"], evidence_response.json()["matches"]

    def test_registered_user_can_login_and_read_profile(self):
        client = self._client()

        register_response = client.post(
            "/api/auth/register",
            json={
                "email": "owner@example.test",
                "password": "registered-password",
                "name": "Practice Owner",
                "organization_name": "Spine Practice",
            },
        )
        self.assertEqual(register_response.status_code, 201, register_response.text)
        token = register_response.json()["access_token"]
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "owner@example.test")
        self.assertEqual(response.json()["role"], "admin")
        self.assertEqual(response.json()["organization"]["name"], "Spine Practice")

        login_response = client.post(
            "/api/auth/login",
            json={"email": "owner@example.test", "password": "registered-password"},
        )
        self.assertEqual(login_response.status_code, 200, login_response.text)

    def test_duplicate_registration_is_rejected(self):
        client = self._client()
        payload = {
            "email": "owner@example.test",
            "password": "registered-password",
            "name": "Practice Owner",
            "organization_name": "Spine Practice",
        }
        first_response = client.post("/api/auth/register", json=payload)
        self.assertEqual(first_response.status_code, 201, first_response.text)

        duplicate_response = client.post("/api/auth/register", json=payload)

        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(duplicate_response.json(), {"error": "An account with this email already exists"})

    def test_forgot_password_issues_reset_token_and_reset_password_rotates_credentials(self):
        client = self._client()
        email = "reset@example.test"
        self._create_test_user(email=email, password="old-password", role="admin")

        forgot_response = client.post("/api/auth/forgot-password", json={"email": email})

        self.assertEqual(forgot_response.status_code, 200, forgot_response.text)
        payload = forgot_response.json()
        self.assertEqual(payload["message"], "If an account exists, password reset instructions have been prepared.")
        self.assertTrue(payload["reset_token"])

        reset_response = client.post(
            "/api/auth/reset-password",
            json={"reset_token": payload["reset_token"], "password": "new-password"},
        )
        self.assertEqual(reset_response.status_code, 200, reset_response.text)

        old_login_response = client.post("/api/auth/login", json={"email": email, "password": "old-password"})
        self.assertEqual(old_login_response.status_code, 401)
        new_login_response = client.post("/api/auth/login", json={"email": email, "password": "new-password"})
        self.assertEqual(new_login_response.status_code, 200, new_login_response.text)

    def test_password_reset_invalidates_existing_access_tokens(self):
        client = self._client()
        email = "reset-session@example.test"
        self._create_test_user(email=email, password="old-password", role="admin")
        login_response = client.post("/api/auth/login", json={"email": email, "password": "old-password"})
        self.assertEqual(login_response.status_code, 200, login_response.text)
        old_access_token = login_response.json()["access_token"]

        forgot_response = client.post("/api/auth/forgot-password", json={"email": email})
        self.assertEqual(forgot_response.status_code, 200, forgot_response.text)
        reset_response = client.post(
            "/api/auth/reset-password",
            json={"reset_token": forgot_response.json()["reset_token"], "password": "new-password"},
        )
        self.assertEqual(reset_response.status_code, 200, reset_response.text)

        stale_me_response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access_token}"})
        self.assertEqual(stale_me_response.status_code, 401)

        new_login_response = client.post("/api/auth/login", json={"email": email, "password": "new-password"})
        self.assertEqual(new_login_response.status_code, 200, new_login_response.text)
        fresh_me_response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {new_login_response.json()['access_token']}"},
        )
        self.assertEqual(fresh_me_response.status_code, 200, fresh_me_response.text)

    def test_forgot_password_invalidates_previous_unused_reset_tokens(self):
        client = self._client()
        email = "reset-rotate@example.test"
        self._create_test_user(email=email, password="old-password", role="admin")

        first_response = client.post("/api/auth/forgot-password", json={"email": email})
        self.assertEqual(first_response.status_code, 200, first_response.text)
        first_token = first_response.json()["reset_token"]

        second_response = client.post("/api/auth/forgot-password", json={"email": email})
        self.assertEqual(second_response.status_code, 200, second_response.text)
        second_token = second_response.json()["reset_token"]

        stale_response = client.post(
            "/api/auth/reset-password",
            json={"reset_token": first_token, "password": "stale-password"},
        )
        self.assertEqual(stale_response.status_code, 400)
        self.assertEqual(stale_response.json(), {"error": "Invalid or expired reset token"})

        reset_response = client.post(
            "/api/auth/reset-password",
            json={"reset_token": second_token, "password": "new-password"},
        )
        self.assertEqual(reset_response.status_code, 200, reset_response.text)

        reuse_response = client.post(
            "/api/auth/reset-password",
            json={"reset_token": second_token, "password": "reused-password"},
        )
        self.assertEqual(reuse_response.status_code, 400)
        self.assertEqual(reuse_response.json(), {"error": "Invalid or expired reset token"})

    def test_production_forgot_password_requires_configured_reset_delivery(self):
        client = self._client()
        email = "reset-production@example.test"
        self._create_test_user(email=email, password="old-password", role="admin")

        original_env = {
            "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
            "PASSWORD_RESET_DELIVERY_MODE": os.environ.get("PASSWORD_RESET_DELIVERY_MODE"),
        }
        os.environ["ENVIRONMENT"] = "production"
        os.environ.pop("PASSWORD_RESET_DELIVERY_MODE", None)
        try:
            response = client.post("/api/auth/forgot-password", json={"email": email})
        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"error": "Password reset delivery is not configured"})

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            token_count = db.scalar(sqlalchemy.select(sqlalchemy.func.count()).select_from(models.PasswordResetToken))

        self.assertEqual(token_count, 0)

    def test_production_forgot_password_with_delivery_config_does_not_expose_reset_token(self):
        client = self._client()
        email = "reset-production-configured@example.test"
        self._create_test_user(email=email, password="old-password", role="admin")

        original_env = {
            "ENVIRONMENT": os.environ.get("ENVIRONMENT"),
            "PASSWORD_RESET_DELIVERY_MODE": os.environ.get("PASSWORD_RESET_DELIVERY_MODE"),
        }
        os.environ["ENVIRONMENT"] = "production"
        os.environ["PASSWORD_RESET_DELIVERY_MODE"] = "external"
        try:
            response = client.post("/api/auth/forgot-password", json={"email": email})
        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["message"], "If an account exists, password reset instructions have been prepared.")
        self.assertIsNone(response.json()["reset_token"])

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

    def test_case_assignment_requires_user_in_current_organization(self):
        client = self._client()
        token = self._login(client)

        response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "patient_label": "SYN-LMRI-ASSIGN",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "prior_auth",
                "assigned_to_user_id": "user_not_in_org",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "Assigned user must belong to the current organization"})

    def test_viewer_cannot_create_cases(self):
        client = self._client()
        token = self._login(client, email="viewer@test.authlens.local")

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
        case_id = self._create_case(client, token, "SYN-LMRI-003")

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

    def test_typed_document_upload_enforces_size_limit(self):
        client = self._client()
        token = self._login(client)
        case_id = self._create_case(client, token, "SYN-LMRI-LARGE")
        original_limit = os.environ.get("MAX_UPLOAD_MB")
        os.environ["MAX_UPLOAD_MB"] = "0.0001"

        try:
            response = client.post(
                f"/api/cases/{case_id}/documents",
                headers={"Authorization": f"Bearer {token}"},
                data={"document_type": "payer_policy"},
                files={"file": ("large.pdf", b"%PDF-1.4\n" + (b"x" * 1024), "application/pdf")},
            )
        finally:
            if original_limit is None:
                os.environ.pop("MAX_UPLOAD_MB", None)
            else:
                os.environ["MAX_UPLOAD_MB"] = original_limit

        self.assertEqual(response.status_code, 413)
        self.assertIn("upload limit", response.json()["error"])

    def test_priorauth_analysis_generates_evidence_report_draft_and_citation_check(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local")
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

    def test_llm_criteria_extraction_invalid_output_fails_closed_without_criteria(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-INVALID")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        try:
            with patch.object(
                llm_gateway,
                "generate_structured_output",
                return_value='{"criteria":[{"criterion_code":"C1","confidence":1.5}]}',
            ):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "LLM output failed schema validation"})

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            runs = list(
                db.scalars(
                    sqlalchemy.select(models.AnalysisRun).where(
                        models.AnalysisRun.case_id == case_id,
                        models.AnalysisRun.run_type == "criteria_extraction",
                    )
                )
            )
            criteria = list(
                db.scalars(sqlalchemy.select(models.PolicyCriterion).where(models.PolicyCriterion.case_id == case_id))
            )

        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0].status, "failed")
        self.assertEqual(runs[0].metadata_json["schema"], "CriteriaExtractionOutput")
        self.assertNotIn("Coverage requires", str(runs[0].metadata_json))
        self.assertNotIn("criterion_code", str(runs[0].metadata_json))
        self.assertEqual(criteria, [])

    def test_llm_criteria_extraction_valid_output_creates_criteria_with_completed_run(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-VALID")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = """
        {
          "criteria": [
            {
              "criterion_code": "C1",
              "criterion_type": "documentation",
              "requirement": "Document six weeks of conservative therapy.",
              "required_evidence": ["Therapy dates"],
              "is_required": true,
              "source_quote": "Coverage requires six weeks of conservative therapy.",
              "source_file": "policy.pdf",
              "source_page": "1",
              "confidence": 0.82,
              "ambiguity_notes": []
            }
          ],
          "missing_or_ambiguous_policy_info": []
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(len(payload["criteria"]), 1)
        self.assertEqual(payload["criteria"][0]["criterion_code"], "C1")
        self.assertEqual(payload["criteria"][0]["source_file"], "policy.pdf")

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            run = db.scalar(
                sqlalchemy.select(models.AnalysisRun).where(
                    models.AnalysisRun.case_id == case_id,
                    models.AnalysisRun.run_type == "criteria_extraction",
                )
            )

        self.assertEqual(run.status, "completed")
        self.assertEqual(run.metadata_json["schema"], "CriteriaExtractionOutput")
        self.assertEqual(run.metadata_json["analysis_mode"], "llm")
        self.assertEqual(run.metadata_json["criteria_count"], 1)

    def test_llm_criteria_extraction_rejects_duplicate_criterion_codes_without_criteria(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-DUP-CRITERIA")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = """
        {
          "criteria": [
            {
              "criterion_code": "C1",
              "criterion_type": "documentation",
              "requirement": "Document six weeks of conservative therapy.",
              "required_evidence": ["Therapy dates"],
              "is_required": true,
              "source_quote": "Coverage requires six weeks of conservative therapy.",
              "source_file": "policy.pdf",
              "source_page": "1",
              "confidence": 0.82,
              "ambiguity_notes": []
            },
            {
              "criterion_code": "C1",
              "criterion_type": "medical_necessity",
              "requirement": "Duplicate code should be rejected.",
              "required_evidence": ["Duplicate"],
              "is_required": true,
              "source_quote": "Coverage requires six weeks of conservative therapy.",
              "source_file": "policy.pdf",
              "source_page": "1",
              "confidence": 0.7,
              "ambiguity_notes": []
            }
          ],
          "missing_or_ambiguous_policy_info": []
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            criteria = list(
                db.scalars(sqlalchemy.select(models.PolicyCriterion).where(models.PolicyCriterion.case_id == case_id))
            )
            run = db.scalar(
                sqlalchemy.select(models.AnalysisRun).where(
                    models.AnalysisRun.case_id == case_id,
                    models.AnalysisRun.run_type == "criteria_extraction",
                )
            )

        self.assertEqual(criteria, [])
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.metadata_json["schema"], "CriteriaExtractionOutput")
        self.assertNotIn("Duplicate code should be rejected", str(run.metadata_json))

    def test_llm_criteria_completed_run_records_resolved_model_version(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-MODEL")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        llm_gateway = importlib.import_module("services.llm_gateway")
        original_env = {
            "PRIORAUTH_ANALYSIS_MODE": os.environ.get("PRIORAUTH_ANALYSIS_MODE"),
            "PRIORAUTH_LLM_MODEL": os.environ.get("PRIORAUTH_LLM_MODEL"),
            "GROQ_MODEL": os.environ.get("GROQ_MODEL"),
        }
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        os.environ["PRIORAUTH_LLM_MODEL"] = ""
        os.environ["GROQ_MODEL"] = "llama-3.3-70b-versatile"
        raw_output = """
        {
          "criteria": [
            {
              "criterion_code": "C1",
              "criterion_type": "documentation",
              "requirement": "Document six weeks of conservative therapy.",
              "required_evidence": ["Therapy dates"],
              "is_required": true,
              "source_quote": "Coverage requires six weeks of conservative therapy.",
              "source_file": "policy.pdf",
              "source_page": "1",
              "confidence": 0.82,
              "ambiguity_notes": []
            }
          ],
          "missing_or_ambiguous_policy_info": []
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.assertEqual(response.status_code, 200, response.text)

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            run = db.scalar(
                sqlalchemy.select(models.AnalysisRun).where(
                    models.AnalysisRun.case_id == case_id,
                    models.AnalysisRun.run_type == "criteria_extraction",
                )
            )

        self.assertEqual(run.model_version, "llama-3.3-70b-versatile")

    def test_llm_criteria_extraction_rejects_ungrounded_citations_without_wiping_existing_criteria(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-UNGROUNDED")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        baseline_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)
        self.assertGreaterEqual(len(baseline_response.json()["criteria"]), 1)

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = """
        {
          "criteria": [
            {
              "criterion_code": "C1",
              "criterion_type": "documentation",
              "requirement": "Fabricated criterion.",
              "required_evidence": ["Fabricated evidence"],
              "is_required": true,
              "source_quote": "This quote is not in the uploaded policy.",
              "source_file": "other-policy.pdf",
              "source_page": "99",
              "confidence": 0.9,
              "ambiguity_notes": []
            }
          ],
          "missing_or_ambiguous_policy_info": []
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": "LLM output failed schema validation"})

        list_response = client.get(
            f"/api/cases/{case_id}/criteria",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(
            [item["criterion_code"] for item in list_response.json()["criteria"]],
            [item["criterion_code"] for item in baseline_response.json()["criteria"]],
        )

    def test_llm_criteria_extraction_rejects_blank_quote_without_wiping_existing_criteria(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-BLANK-QUOTE")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        baseline_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = """
        {
          "criteria": [
            {
              "criterion_code": "C1",
              "criterion_type": "documentation",
              "requirement": "Document six weeks of conservative therapy.",
              "required_evidence": ["Therapy dates"],
              "is_required": true,
              "source_quote": "   ",
              "source_file": "policy.pdf",
              "source_page": "1",
              "confidence": 0.82,
              "ambiguity_notes": []
            }
          ],
          "missing_or_ambiguous_policy_info": []
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        list_response = client.get(
            f"/api/cases/{case_id}/criteria",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(
            [item["criterion_code"] for item in list_response.json()["criteria"]],
            [item["criterion_code"] for item in baseline_response.json()["criteria"]],
        )

    def test_llm_criteria_extraction_rejects_empty_output_without_wiping_existing_criteria(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-EMPTY")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        baseline_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value='{"criteria": []}'):
                response = client.post(
                    f"/api/cases/{case_id}/criteria/extract",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        list_response = client.get(
            f"/api/cases/{case_id}/criteria",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(
            [item["criterion_code"] for item in list_response.json()["criteria"]],
            [item["criterion_code"] for item in baseline_response.json()["criteria"]],
        )

    def test_llm_criteria_generation_failure_records_each_attempt(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-PROVIDER-FAIL")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        try:
            for _ in range(2):
                with patch.object(
                    llm_gateway,
                    "generate_structured_output",
                    side_effect=llm_gateway.StructuredOutputError("provider unavailable"),
                ):
                    response = client.post(
                        f"/api/cases/{case_id}/criteria/extract",
                        headers={"Authorization": f"Bearer {coordinator_token}"},
                    )
                    self.assertEqual(response.status_code, 502)
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            runs = list(
                db.scalars(
                    sqlalchemy.select(models.AnalysisRun)
                    .where(
                        models.AnalysisRun.case_id == case_id,
                        models.AnalysisRun.run_type == "criteria_extraction",
                        models.AnalysisRun.status == "failed",
                    )
                    .order_by(models.AnalysisRun.created_at)
                )
            )

        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run.metadata_json["error_type"] == "StructuredOutputError" for run in runs))

    def test_llm_criteria_generation_failure_with_cause_records_each_attempt(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-PROVIDER-CAUSE")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        llm_gateway = importlib.import_module("services.llm_gateway")

        def fail_with_provider_cause(_prompt, **_kwargs):
            try:
                raise RuntimeError("provider unavailable")
            except RuntimeError as exc:
                raise llm_gateway.StructuredOutputError("provider unavailable") from exc

        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        try:
            for _ in range(2):
                with patch.object(llm_gateway, "generate_structured_output", side_effect=fail_with_provider_cause):
                    response = client.post(
                        f"/api/cases/{case_id}/criteria/extract",
                        headers={"Authorization": f"Bearer {coordinator_token}"},
                    )
                    self.assertEqual(response.status_code, 502)
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            runs = list(
                db.scalars(
                    sqlalchemy.select(models.AnalysisRun)
                    .where(
                        models.AnalysisRun.case_id == case_id,
                        models.AnalysisRun.run_type == "criteria_extraction",
                        models.AnalysisRun.status == "failed",
                    )
                    .order_by(models.AnalysisRun.created_at)
                )
            )

        self.assertEqual(len(runs), 2)
        self.assertTrue(all(run.metadata_json["error_type"] == "StructuredOutputError" for run in runs))

    def test_llm_evidence_matching_grounds_met_matches_to_patient_documents_only(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-EVIDENCE")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "patient_note",
            "note.pdf",
            b"%PDF-1.4\nThe patient completed six weeks of conservative therapy.",
        )
        criteria_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(criteria_response.status_code, 200, criteria_response.text)
        criterion_code = criteria_response.json()["criteria"][0]["criterion_code"]

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = f"""
        {{
          "matches": [
            {{
              "criterion_code": "{criterion_code}",
              "status": "met",
              "evidence_summary": "The patient note supports conservative therapy documentation.",
              "source_quote": "The patient completed six weeks of conservative therapy.",
              "source_file": "note.pdf",
              "source_page": "1",
              "why_it_matters": "This patient-document citation supports the payer criterion.",
              "missing_evidence": [],
              "conflicting_evidence": [],
              "recommended_action": "Clinician reviewer should confirm this citation.",
              "confidence": 0.84
            }}
          ]
        }}
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/evidence/match",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 200, response.text)
        matches = response.json()["matches"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["status"], "met")
        self.assertEqual(matches[0]["source_file"], "note.pdf")

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            match = db.scalar(sqlalchemy.select(models.EvidenceMatch).where(models.EvidenceMatch.case_id == case_id))
            run = db.scalar(
                sqlalchemy.select(models.AnalysisRun).where(
                    models.AnalysisRun.case_id == case_id,
                    models.AnalysisRun.run_type == "evidence_matching",
                )
            )
            source_document = db.get(models.Document, match.source_document_id)

        self.assertEqual(source_document.document_type, "patient_note")
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.metadata_json["schema"], "EvidenceMatchingOutput")
        self.assertEqual(run.metadata_json["analysis_mode"], "llm")

    def test_llm_evidence_matching_rejects_policy_document_citation_without_wiping_existing_matches(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-LLM-EVIDENCE-POLICY")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "patient_note",
            "note.pdf",
            b"%PDF-1.4\nThe patient completed six weeks of conservative therapy.",
        )
        criteria_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(criteria_response.status_code, 200, criteria_response.text)
        baseline_response = client.post(
            f"/api/cases/{case_id}/evidence/match",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)
        criterion_code = criteria_response.json()["criteria"][0]["criterion_code"]

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = f"""
        {{
          "matches": [
            {{
              "criterion_code": "{criterion_code}",
              "status": "met",
              "evidence_summary": "This incorrectly cites the payer policy as patient evidence.",
              "source_quote": "Coverage requires six weeks of conservative therapy.",
              "source_file": "policy.pdf",
              "source_page": "1",
              "why_it_matters": "This should be rejected because it is not a patient document.",
              "missing_evidence": [],
              "conflicting_evidence": [],
              "recommended_action": "Retry evidence matching.",
              "confidence": 0.9
            }}
          ]
        }}
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/evidence/match",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        list_response = client.get(
            f"/api/cases/{case_id}/evidence",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(
            [item["id"] for item in list_response.json()["matches"]],
            [item["id"] for item in baseline_response.json()["matches"]],
        )

    def test_llm_evidence_matching_rejects_duplicate_stored_criterion_codes_without_wiping_existing_matches(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id, criteria, baseline_matches = self._prepare_case_with_policy_and_note(client, coordinator_token)

        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            criterion = db.scalar(
                sqlalchemy.select(models.PolicyCriterion).where(models.PolicyCriterion.case_id == case_id).limit(1)
            )
            duplicate = models.PolicyCriterion(
                organization_id=criterion.organization_id,
                case_id=criterion.case_id,
                analysis_run_id=criterion.analysis_run_id,
                criterion_code=criterion.criterion_code,
                criterion_type=criterion.criterion_type,
                requirement="Duplicate criterion code should fail closed.",
                required_evidence=["Duplicate should not collapse evidence matching."],
                is_required=criterion.is_required,
                source_document_id=criterion.source_document_id,
                source_file=criterion.source_file,
                source_page=criterion.source_page,
                source_quote=criterion.source_quote,
                confidence=criterion.confidence,
                ambiguity_notes=[],
                extraction_version=criterion.extraction_version,
            )
            db.add(duplicate)
            db.commit()

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = json.dumps(
            {
                "matches": [
                    {
                        "criterion_code": unique_code,
                        "status": "met",
                        "evidence_summary": "The patient note supports conservative therapy documentation.",
                        "source_quote": "six weeks of conservative therapy",
                        "source_file": "note.pdf",
                        "source_page": "1",
                        "why_it_matters": "This patient-document citation supports the payer criterion.",
                        "missing_evidence": [],
                        "conflicting_evidence": [],
                        "recommended_action": "Clinician reviewer should confirm this citation.",
                        "confidence": 0.84,
                    }
                    for unique_code in sorted({item["criterion_code"] for item in criteria})
                ]
            }
        )
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/evidence/match",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        list_response = client.get(
            f"/api/cases/{case_id}/evidence",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(
            [item["id"] for item in list_response.json()["matches"]],
            [item["id"] for item in baseline_matches],
        )

    def test_llm_readiness_report_persists_structured_documentation_completeness_report(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id, _criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        baseline_response = client.get(
            f"/api/cases/{case_id}/reports/latest",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)
        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = """
        {
          "readiness_score": 75,
          "overall_status": "needs_more_documentation",
          "summary": "This readiness score reflects documentation completeness only.",
          "highest_risk_items": ["C1: Clinician should review the conservative therapy citation."],
          "recommended_next_steps": ["Clinician reviewer should confirm citation quality before submission."]
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/reports/readiness",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 200, response.text)
        report = response.json()
        self.assertEqual(report["readiness_score"], baseline_response.json()["readiness_score"])
        self.assertEqual(report["overall_status"], baseline_response.json()["overall_status"])
        self.assertEqual(report["report_json"]["score_interpretation"], "documentation completeness only")
        self.assertEqual(report["report_json"]["analysis_mode"], "llm")

    def test_llm_readiness_invalid_output_fails_closed_without_replacing_latest_report(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id, _criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        baseline_response = client.get(
            f"/api/cases/{case_id}/reports/latest",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        try:
            with patch.object(
                llm_gateway,
                "generate_structured_output",
                return_value='{"readiness_score":150,"overall_status":"ready_for_review","summary":"Invalid"}',
            ):
                response = client.post(
                    f"/api/cases/{case_id}/reports/readiness",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        latest_response = client.get(
            f"/api/cases/{case_id}/reports/latest",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(latest_response.json()["id"], baseline_response.json()["id"])

    def test_llm_readiness_unsafe_list_output_fails_closed_without_replacing_latest_report(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id, _criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        baseline_response = client.get(
            f"/api/cases/{case_id}/reports/latest",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(baseline_response.status_code, 200, baseline_response.text)

        llm_gateway = importlib.import_module("services.llm_gateway")
        original_mode = os.environ.get("PRIORAUTH_ANALYSIS_MODE")
        os.environ["PRIORAUTH_ANALYSIS_MODE"] = "llm"
        raw_output = """
        {
          "readiness_score": 75,
          "overall_status": "needs_more_documentation",
          "summary": "This readiness score reflects documentation completeness only.",
          "highest_risk_items": ["Approval is likely after reviewer confirmation."],
          "recommended_next_steps": ["Start physical therapy before submission."]
        }
        """
        try:
            with patch.object(llm_gateway, "generate_structured_output", return_value=raw_output):
                response = client.post(
                    f"/api/cases/{case_id}/reports/readiness",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
        finally:
            if original_mode is None:
                os.environ.pop("PRIORAUTH_ANALYSIS_MODE", None)
            else:
                os.environ["PRIORAUTH_ANALYSIS_MODE"] = original_mode

        self.assertEqual(response.status_code, 502)
        latest_response = client.get(
            f"/api/cases/{case_id}/reports/latest",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(latest_response.json()["id"], baseline_response.json()["id"])

    def test_draft_edit_blocks_approval_until_citations_are_reverified(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local")
        case_id, _criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/prior-auth",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        draft = draft_response.json()
        check_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(check_response.status_code, 200, check_response.text)
        self.assertEqual(check_response.json()["verification_status"], "pass")

        edit_response = client.patch(
            f"/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={"content_markdown": draft["content_markdown"] + "\nThis patient qualifies."},
        )
        self.assertEqual(edit_response.status_code, 200, edit_response.text)
        self.assertEqual(edit_response.json()["status"], "needs_revision")

        approve_response = client.post(
            f"/api/drafts/{draft['id']}/approve",
            headers={"Authorization": f"Bearer {clinician_token}"},
        )

        self.assertEqual(approve_response.status_code, 400)
        self.assertEqual(approve_response.json(), {"error": "Draft must be citation-verified after the latest edit"})

    def test_citation_verification_fails_when_human_review_disclaimer_is_removed(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id, _criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/prior-auth",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        draft = draft_response.json()
        edited_content = draft["content_markdown"].replace(
            "Clinician review is required before submission. This draft does not diagnose, recommend treatment, or guarantee payer approval.",
            "Ready for submission.",
        )
        edit_response = client.patch(
            f"/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={"content_markdown": edited_content},
        )
        self.assertEqual(edit_response.status_code, 200, edit_response.text)

        check_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(check_response.status_code, 200, check_response.text)
        payload = check_response.json()
        self.assertEqual(payload["verification_status"], "fail")
        self.assertTrue(
            any("human review disclaimer" in claim["issue"].lower() for claim in payload["unsupported_claims"])
        )

    def test_met_override_requires_existing_citation_and_low_readiness_serializes(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local")
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-MISSING")
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        criteria_response = client.post(
            f"/api/cases/{case_id}/criteria/extract",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(criteria_response.status_code, 200, criteria_response.text)
        evidence_response = client.post(
            f"/api/cases/{case_id}/evidence/match",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(evidence_response.status_code, 200, evidence_response.text)
        match = evidence_response.json()["matches"][0]
        self.assertEqual(match["status"], "not_found")

        override_response = client.patch(
            f"/api/evidence-matches/{match['id']}",
            headers={"Authorization": f"Bearer {clinician_token}"},
            json={"reviewer_override_status": "met", "reviewer_override_reason": "Manual review"},
        )
        self.assertEqual(override_response.status_code, 400)
        self.assertEqual(
            override_response.json(),
            {"error": "A met override requires source quote, file, page, and rationale"},
        )

        report_response = client.post(
            f"/api/cases/{case_id}/reports/readiness",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertEqual(report_response.json()["overall_status"], "needs_more_documentation")
        list_response = client.get("/api/cases", headers={"Authorization": f"Bearer {coordinator_token}"})
        self.assertEqual(list_response.status_code, 200, list_response.text)
        self.assertEqual(list_response.json()["cases"][0]["status"], "needs_more_documentation")

    def test_evidence_overrides_control_readiness_drafts_and_citation_verification(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local")
        case_id, _criteria, matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        met_matches = [match for match in matches if match["status"] == "met"]
        self.assertGreater(len(met_matches), 0)

        for match in met_matches:
            override_response = client.patch(
                f"/api/evidence-matches/{match['id']}",
                headers={"Authorization": f"Bearer {clinician_token}"},
                json={"reviewer_override_status": "not_met", "reviewer_override_reason": "Citation does not satisfy policy"},
            )
            self.assertEqual(override_response.status_code, 200, override_response.text)

        report_response = client.post(
            f"/api/cases/{case_id}/reports/readiness",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(report_response.status_code, 200, report_response.text)
        self.assertLess(report_response.json()["readiness_score"], 100)

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/prior-auth",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        self.assertNotIn("provided documents indicate supporting evidence", draft_response.json()["content_markdown"].lower())

    def test_appeal_draft_uses_denial_letter_reason_and_verified_evidence(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={
                "patient_label": "SYN-LMRI-APPEAL",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "appeal",
            },
        )
        self.assertEqual(case_response.status_code, 201, case_response.text)
        case_id = case_response.json()["id"]
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy. Functional limitation must be documented.",
        )
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "patient_note",
            "note.pdf",
            b"%PDF-1.4\nThe provided documents indicate six weeks of conservative therapy and functional limitation with walking.",
        )
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "denial_letter",
            "denial.pdf",
            b"%PDF-1.4\nThe request was denied as not medically necessary due to insufficient conservative therapy documentation.",
        )
        for path in [
            f"/api/cases/{case_id}/criteria/extract",
            f"/api/cases/{case_id}/evidence/match",
            f"/api/cases/{case_id}/reports/readiness",
        ]:
            response = client.post(path, headers={"Authorization": f"Bearer {coordinator_token}"})
            self.assertEqual(response.status_code, 200, response.text)

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/appeal",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        draft = draft_response.json()
        content = draft["content_markdown"]
        lowered = content.lower()
        self.assertEqual(draft["letter_type"], "appeal")
        self.assertIn("not medically necessary", lowered)
        self.assertIn("insufficient conservative therapy documentation", lowered)
        self.assertIn("Clinician review is required", content)
        self.assertIn("[denial.pdf, page 1]", content)
        self.assertIn("[note.pdf, page 1]", content)
        self.assertNotIn("guaranteed approval", lowered)
        self.assertNotIn("must approve", lowered)
        self.assertNotIn("this patient qualifies", lowered)

        wrong_draft_response = client.post(
            f"/api/cases/{case_id}/drafts/prior-auth",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(wrong_draft_response.status_code, 400)
        self.assertEqual(wrong_draft_response.json(), {"error": "Prior authorization drafts require a prior-auth case"})

        check_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(check_response.status_code, 200, check_response.text)
        self.assertEqual(check_response.json()["verification_status"], "pass")

        edit_response = client.patch(
            f"/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={"content_markdown": content.replace("[denial.pdf, page 1]", "")},
        )
        self.assertEqual(edit_response.status_code, 200, edit_response.text)
        recheck_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(recheck_response.status_code, 200, recheck_response.text)
        self.assertEqual(recheck_response.json()["verification_status"], "fail")
        self.assertTrue(
            any("denial reason" in claim["claim"].lower() for claim in recheck_response.json()["unsupported_claims"])
        )

        moved_citation_content = content.replace("[denial.pdf, page 1]", "") + "\nReference: [denial.pdf, page 1]"
        moved_edit_response = client.patch(
            f"/api/drafts/{draft['id']}",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={"content_markdown": moved_citation_content},
        )
        self.assertEqual(moved_edit_response.status_code, 200, moved_edit_response.text)
        moved_recheck_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(moved_recheck_response.status_code, 200, moved_recheck_response.text)
        self.assertEqual(moved_recheck_response.json()["verification_status"], "fail")
        self.assertTrue(
            any("denial reason" in claim["claim"].lower() for claim in moved_recheck_response.json()["unsupported_claims"])
        )

    def test_appeal_draft_requires_denial_letter(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={
                "patient_label": "SYN-LMRI-APPEAL-MISSING",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "appeal",
            },
        )
        self.assertEqual(case_response.status_code, 201, case_response.text)
        case_id = case_response.json()["id"]
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "payer_policy",
            "policy.pdf",
            b"%PDF-1.4\nCoverage requires six weeks of conservative therapy.",
        )
        self._upload_document(
            client,
            coordinator_token,
            case_id,
            "patient_note",
            "note.pdf",
            b"%PDF-1.4\nThe provided documents indicate six weeks of conservative therapy.",
        )
        for path in [
            f"/api/cases/{case_id}/criteria/extract",
            f"/api/cases/{case_id}/evidence/match",
            f"/api/cases/{case_id}/reports/readiness",
        ]:
            response = client.post(path, headers={"Authorization": f"Bearer {coordinator_token}"})
            self.assertEqual(response.status_code, 200, response.text)

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/appeal",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(draft_response.status_code, 400)
        self.assertEqual(draft_response.json(), {"error": "Upload a denial letter before drafting an appeal"})

    def test_appeal_draft_requires_denial_letter_before_readiness_report(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {coordinator_token}"},
            json={
                "patient_label": "SYN-LMRI-APPEAL-NO-REPORT",
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI",
                "case_type": "appeal",
            },
        )
        self.assertEqual(case_response.status_code, 201, case_response.text)
        case_id = case_response.json()["id"]

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/appeal",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(draft_response.status_code, 400)
        self.assertEqual(draft_response.json(), {"error": "Upload a denial letter before drafting an appeal"})

    def test_appeal_draft_requires_appeal_case_type(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-PRIOR-AUTH-NOT-APPEAL")

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/appeal",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(draft_response.status_code, 400)
        self.assertEqual(draft_response.json(), {"error": "Appeal drafts require an appeal case"})

    def test_clinician_can_audit_update_criteria_without_losing_source_provenance(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local")
        _case_id, criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        criterion = criteria[0]

        response = client.patch(
            f"/api/criteria/{criterion['id']}",
            headers={"Authorization": f"Bearer {clinician_token}"},
            json={
                "requirement": "Document at least six weeks of conservative therapy.",
                "required_evidence": ["Therapy dates", "Clinical note"],
                "reviewer_status": "reviewed",
            },
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["requirement"], "Document at least six weeks of conservative therapy.")
        self.assertEqual(payload["required_evidence"], ["Therapy dates", "Clinical note"])
        self.assertEqual(payload["reviewer_status"], "reviewed")
        self.assertEqual(payload["source_file"], criterion["source_file"])

    def test_case_summary_ignores_mismatched_child_row_tenants(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id, _criteria, _matches = self._prepare_case_with_policy_and_note(client, coordinator_token)
        before_response = client.get(
            f"/api/cases/{case_id}",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(before_response.status_code, 200, before_response.text)
        before_missing_count = before_response.json()["missing_required_criteria_count"]

        self._create_test_user(
            email="other-admin@test.authlens.local",
            password="test-password",
            role="admin",
            organization_id="org_other_spine",
            organization_name="Other Spine Clinic",
        )
        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        with session.SessionLocal() as db:
            db.add(
                models.PolicyCriterion(
                    organization_id="org_other_spine",
                    case_id=case_id,
                    criterion_code="ROGUE",
                    criterion_type="documentation",
                    requirement="Rogue cross-tenant criterion should never affect this case summary.",
                    required_evidence=["Cross-tenant evidence"],
                    is_required=True,
                    source_file="rogue-policy.pdf",
                    source_page="1",
                    source_quote="Rogue requirement",
                    confidence=0.1,
                    ambiguity_notes=[],
                )
            )
            db.commit()

        after_response = client.get(
            f"/api/cases/{case_id}",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(after_response.status_code, 200, after_response.text)
        self.assertEqual(after_response.json()["missing_required_criteria_count"], before_missing_count)

    def test_cross_tenant_direct_id_routes_are_denied(self):
        client = self._client()
        coordinator_token = self._login(client)
        self._create_test_user(
            email="other-admin@test.authlens.local",
            password="test-password",
            role="admin",
            organization_id="org_other_spine",
            organization_name="Other Spine Clinic",
        )
        other_org_token = self._login(client, email="other-admin@test.authlens.local")
        case_id, criteria, matches = self._prepare_case_with_policy_and_note(client, coordinator_token)

        documents_response = client.get(
            f"/api/cases/{case_id}/documents",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(documents_response.status_code, 200, documents_response.text)
        document_id = documents_response.json()["documents"][0]["id"]

        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/prior-auth",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        draft_id = draft_response.json()["id"]

        headers = {"Authorization": f"Bearer {other_org_token}"}
        denied_requests = [
            ("get case", lambda: client.get(f"/api/cases/{case_id}", headers=headers)),
            (
                "patch case",
                lambda: client.patch(
                    f"/api/cases/{case_id}",
                    headers=headers,
                    json={"patient_label": "SYN-LMRI-CROSS-TENANT"},
                ),
            ),
            ("archive case", lambda: client.post(f"/api/cases/{case_id}/archive", headers=headers)),
            ("list documents", lambda: client.get(f"/api/cases/{case_id}/documents", headers=headers)),
            ("get document", lambda: client.get(f"/api/documents/{document_id}", headers=headers)),
            ("extract criteria", lambda: client.post(f"/api/cases/{case_id}/criteria/extract", headers=headers)),
            ("list criteria", lambda: client.get(f"/api/cases/{case_id}/criteria", headers=headers)),
            (
                "patch criterion",
                lambda: client.patch(
                    f"/api/criteria/{criteria[0]['id']}",
                    headers=headers,
                    json={"reviewer_status": "reviewed"},
                ),
            ),
            ("match evidence", lambda: client.post(f"/api/cases/{case_id}/evidence/match", headers=headers)),
            ("list evidence", lambda: client.get(f"/api/cases/{case_id}/evidence", headers=headers)),
            (
                "patch evidence match",
                lambda: client.patch(
                    f"/api/evidence-matches/{matches[0]['id']}",
                    headers=headers,
                    json={
                        "reviewer_override_status": "not_met",
                        "reviewer_override_reason": "Cross-tenant attempt",
                    },
                ),
            ),
            ("latest readiness report", lambda: client.get(f"/api/cases/{case_id}/reports/latest", headers=headers)),
            ("create readiness report", lambda: client.post(f"/api/cases/{case_id}/reports/readiness", headers=headers)),
            ("create prior-auth draft", lambda: client.post(f"/api/cases/{case_id}/drafts/prior-auth", headers=headers)),
            ("list drafts", lambda: client.get(f"/api/cases/{case_id}/drafts", headers=headers)),
            ("deferred appeal draft", lambda: client.post(f"/api/cases/{case_id}/drafts/appeal", headers=headers)),
            ("get draft", lambda: client.get(f"/api/drafts/{draft_id}", headers=headers)),
            (
                "patch draft",
                lambda: client.patch(
                    f"/api/drafts/{draft_id}",
                    headers=headers,
                    json={"content_markdown": "Cross-tenant edit attempt"},
                ),
            ),
            ("verify citations", lambda: client.post(f"/api/drafts/{draft_id}/verify-citations", headers=headers)),
            ("approve draft", lambda: client.post(f"/api/drafts/{draft_id}/approve", headers=headers)),
            ("case audit", lambda: client.get(f"/api/cases/{case_id}/audit", headers=headers)),
        ]

        for label, request in denied_requests:
            with self.subTest(label=label):
                response = request()
                self.assertEqual(response.status_code, 404, response.text)

    def test_case_audit_is_scoped_to_the_case_and_org_wide_audit_is_admin_only(self):
        client = self._client()
        coordinator_token = self._login(client)
        admin_token = self._login(client, email="admin@test.authlens.local")
        other_org_admin_id = self._create_test_user(
            email="other-admin@test.authlens.local",
            password="test-password",
            role="admin",
            organization_id="org_other_spine",
            organization_name="Other Spine Clinic",
        )
        self.assertTrue(other_org_admin_id)
        other_org_token = self._login(client, email="other-admin@test.authlens.local")
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-AUDIT")

        case_audit_response = client.get(
            f"/api/cases/{case_id}/audit",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(case_audit_response.status_code, 200, case_audit_response.text)
        case_events = case_audit_response.json()["events"]
        self.assertGreaterEqual(len(case_events), 1)
        self.assertTrue(all(event["case_id"] == case_id for event in case_events))
        self.assertIn("case.created", {event["action"] for event in case_events})
        self.assertNotIn("patient document", str(case_events).lower())

        cross_org_response = client.get(
            f"/api/cases/{case_id}/audit",
            headers={"Authorization": f"Bearer {other_org_token}"},
        )
        self.assertEqual(cross_org_response.status_code, 404)

        org_audit_response = client.get("/api/audit", headers={"Authorization": f"Bearer {admin_token}"})
        self.assertEqual(org_audit_response.status_code, 200, org_audit_response.text)
        org_events = org_audit_response.json()["events"]
        self.assertIn("case.created", {event["action"] for event in org_events})

        coordinator_org_audit_response = client.get(
            "/api/audit",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(coordinator_org_audit_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
