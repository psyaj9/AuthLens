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
