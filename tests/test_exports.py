import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class ExportWorkflowTests(unittest.TestCase):
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
            "routes.exports",
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

    def _create_test_user(
        self,
        email="coordinator@test.authlens.local",
        password="test-password",
        role="coordinator",
        name="Test User",
        organization_id="org_test_spine",
        organization_name="Test Spine Clinic",
    ):
        session = importlib.import_module("db.session")
        models = importlib.import_module("models.priorauth")
        auth = importlib.import_module("modules.auth")
        sqlalchemy = importlib.import_module("sqlalchemy")
        with session.SessionLocal() as db:
            org = db.get(models.Organization, organization_id)
            if org is None:
                org = models.Organization(id=organization_id, name=organization_name, plan="test")
                db.add(org)
            user = db.scalar(sqlalchemy.select(models.User).where(models.User.email == email))
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
                sqlalchemy.select(models.OrganizationMembership).where(
                    models.OrganizationMembership.user_id == user.id,
                    models.OrganizationMembership.organization_id == org.id,
                )
            )
            if membership is None:
                db.add(
                    models.OrganizationMembership(
                        user_id=user.id,
                        organization_id=org.id,
                        role=role,
                    )
                )
            else:
                membership.role = role
            db.commit()
            return user.id

    def _login(self, client, email="coordinator@test.authlens.local", role="coordinator"):
        self._create_test_user(email=email, role=role)
        response = client.post(
            "/api/auth/login",
            json={"email": email, "password": "test-password"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def _create_case(self, client, token, patient_label="SYN-LMRI-EXPORT", case_type="prior_auth"):
        response = client.post(
            "/api/cases",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "patient_label": patient_label,
                "payer_name": "Example Health Plan",
                "specialty": "Radiology",
                "requested_service": "Lumbar spine MRI appeal" if case_type == "appeal" else "Lumbar spine MRI",
                "case_type": case_type,
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

    def _prepare_analyzed_case(
        self,
        client,
        token,
        patient_label="SYN-LMRI-EXPORT",
        case_type="prior_auth",
        include_denial_letter=False,
    ):
        case_id = self._create_case(client, token, patient_label=patient_label, case_type=case_type)
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
        if include_denial_letter:
            self._upload_document(
                client,
                token,
                case_id,
                "denial_letter",
                "denial.pdf",
                b"%PDF-1.4\nDenial reason: request denied as not medically necessary because conservative therapy was not shown.",
            )
        for path in [
            f"/api/cases/{case_id}/criteria/extract",
            f"/api/cases/{case_id}/evidence/match",
            f"/api/cases/{case_id}/reports/readiness",
        ]:
            response = client.post(path, headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(response.status_code, 200, response.text)
        return case_id

    def _create_verified_draft(self, client, token, case_id, letter_type="prior_auth"):
        draft_path = "appeal" if letter_type == "appeal" else "prior-auth"
        draft_response = client.post(
            f"/api/cases/{case_id}/drafts/{draft_path}",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.text)
        draft = draft_response.json()
        self.assertEqual(draft["letter_type"], letter_type)
        check_response = client.post(
            f"/api/drafts/{draft['id']}/verify-citations",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(check_response.status_code, 200, check_response.text)
        self.assertEqual(check_response.json()["verification_status"], "pass")
        return draft

    def test_readiness_export_requires_existing_report_and_exports_report(self):
        client = self._client()
        coordinator_token = self._login(client)
        case_id = self._create_case(client, coordinator_token, "SYN-LMRI-NO-REPORT")

        missing_response = client.post(
            f"/api/cases/{case_id}/exports/readiness-report",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(missing_response.status_code, 400)
        self.assertEqual(missing_response.json(), {"error": "Generate a readiness report before exporting"})

        analyzed_case_id = self._prepare_analyzed_case(client, coordinator_token)
        export_response = client.post(
            f"/api/cases/{analyzed_case_id}/exports/readiness-report",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(export_response.status_code, 201, export_response.text)
        payload = export_response.json()
        self.assertEqual(payload["export_type"], "readiness_report")
        self.assertTrue(payload["file_name"].endswith("-readiness-report.pdf"))
        self.assertEqual(payload["mime_type"], "application/pdf")
        self.assertIn("documentation completeness", payload["content_markdown"])
        self.assertEqual(payload["manifest_json"]["synthetic_only"], True)

    def test_letter_and_packet_exports_require_approved_draft(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local", role="clinician_reviewer")
        case_id = self._prepare_analyzed_case(client, coordinator_token)
        draft = self._create_verified_draft(client, coordinator_token, case_id)

        for export_path in ["letter", "packet"]:
            with self.subTest(export_path=export_path):
                response = client.post(
                    f"/api/cases/{case_id}/exports/{export_path}",
                    headers={"Authorization": f"Bearer {coordinator_token}"},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json(), {"error": "Approved draft required before export"})

        approve_response = client.post(
            f"/api/drafts/{draft['id']}/approve",
            headers={"Authorization": f"Bearer {clinician_token}"},
        )
        self.assertEqual(approve_response.status_code, 200, approve_response.text)

        letter_response = client.post(
            f"/api/cases/{case_id}/exports/letter",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        packet_response = client.post(
            f"/api/cases/{case_id}/exports/packet",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(letter_response.status_code, 201, letter_response.text)
        self.assertIn("Clinician review is required", letter_response.json()["content_markdown"])
        self.assertNotIn("guaranteed approval", letter_response.json()["content_markdown"].lower())
        self.assertEqual(packet_response.status_code, 201, packet_response.text)
        self.assertTrue(letter_response.json()["file_name"].endswith("-prior-auth-letter.pdf"))
        self.assertEqual(letter_response.json()["mime_type"], "application/pdf")
        packet = packet_response.json()
        self.assertEqual(packet["export_type"], "packet")
        self.assertTrue(packet["file_name"].endswith("-prior-auth-packet.pdf"))
        self.assertEqual(packet["mime_type"], "application/pdf")
        self.assertGreaterEqual(len(packet["manifest_json"]["documents"]), 2)
        self.assertGreaterEqual(len(packet["manifest_json"]["citations"]), 1)
        self.assertIn("policy.pdf", packet["content_markdown"])
        self.assertIn("note.pdf", packet["content_markdown"])

        case_response = client.get(f"/api/cases/{case_id}", headers={"Authorization": f"Bearer {coordinator_token}"})
        self.assertEqual(case_response.json()["status"], "exported")

    def test_appeal_letter_and_packet_exports_use_approved_appeal_draft(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local", role="clinician_reviewer")
        case_id = self._prepare_analyzed_case(
            client,
            coordinator_token,
            patient_label="SYN-LMRI-APPEAL-EXPORT",
            case_type="appeal",
            include_denial_letter=True,
        )
        draft = self._create_verified_draft(client, coordinator_token, case_id, letter_type="appeal")
        approve_response = client.post(
            f"/api/drafts/{draft['id']}/approve",
            headers={"Authorization": f"Bearer {clinician_token}"},
        )
        self.assertEqual(approve_response.status_code, 200, approve_response.text)

        letter_response = client.post(
            f"/api/cases/{case_id}/exports/letter",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        packet_response = client.post(
            f"/api/cases/{case_id}/exports/packet",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )

        self.assertEqual(letter_response.status_code, 201, letter_response.text)
        letter = letter_response.json()
        self.assertTrue(letter["file_name"].endswith("-appeal-letter.pdf"))
        self.assertIn("# Appeal Letter: SYN-LMRI-APPEAL-EXPORT", letter["content_markdown"])
        self.assertIn("Denial reason identified from payer letter", letter["content_markdown"])
        self.assertEqual(letter["manifest_json"]["draft_letter_id"], draft["id"])
        self.assertEqual(letter["manifest_json"]["draft_letter_type"], "appeal")

        self.assertEqual(packet_response.status_code, 201, packet_response.text)
        packet = packet_response.json()
        self.assertTrue(packet["file_name"].endswith("-appeal-packet.pdf"))
        self.assertIn("# Appeal Packet: SYN-LMRI-APPEAL-EXPORT", packet["content_markdown"])
        self.assertEqual(packet["manifest_json"]["draft_letter_id"], draft["id"])
        self.assertEqual(packet["manifest_json"]["draft_letter_type"], "appeal")

    def test_cross_org_cannot_download_export(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local", role="clinician_reviewer")
        self._create_test_user(
            email="other-admin@test.authlens.local",
            role="admin",
            organization_id="org_other_spine",
            organization_name="Other Spine Clinic",
        )
        other_org_token = self._login(client, email="other-admin@test.authlens.local", role="admin")
        case_id = self._prepare_analyzed_case(client, coordinator_token)
        draft = self._create_verified_draft(client, coordinator_token, case_id)
        approve_response = client.post(
            f"/api/drafts/{draft['id']}/approve",
            headers={"Authorization": f"Bearer {clinician_token}"},
        )
        self.assertEqual(approve_response.status_code, 200, approve_response.text)
        export_response = client.post(
            f"/api/cases/{case_id}/exports/packet",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(export_response.status_code, 201, export_response.text)
        export_id = export_response.json()["id"]

        download_response = client.get(
            f"/api/exports/{export_id}/download",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(download_response.status_code, 200, download_response.text)
        self.assertIn("application/pdf", download_response.headers["content-type"])
        self.assertIn("attachment", download_response.headers["content-disposition"])
        self.assertIn(".pdf", download_response.headers["content-disposition"])
        self.assertEqual(download_response.headers["x-content-type-options"], "nosniff")
        self.assertTrue(download_response.content.startswith(b"%PDF-"))
        self.assertIn(b"Synthetic/de-identified use only", download_response.content)

        cross_org_response = client.get(
            f"/api/exports/{export_id}/download",
            headers={"Authorization": f"Bearer {other_org_token}"},
        )
        self.assertEqual(cross_org_response.status_code, 404)

    def test_export_creation_requires_allowed_role_and_same_org_case(self):
        client = self._client()
        coordinator_token = self._login(client)
        viewer_token = self._login(client, email="viewer@test.authlens.local", role="viewer")
        self._create_test_user(
            email="other-admin@test.authlens.local",
            role="admin",
            organization_id="org_other_spine",
            organization_name="Other Spine Clinic",
        )
        other_org_token = self._login(client, email="other-admin@test.authlens.local", role="admin")
        case_id = self._prepare_analyzed_case(client, coordinator_token)

        viewer_response = client.post(
            f"/api/cases/{case_id}/exports/readiness-report",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        self.assertEqual(viewer_response.status_code, 403)

        cross_org_response = client.post(
            f"/api/cases/{case_id}/exports/readiness-report",
            headers={"Authorization": f"Bearer {other_org_token}"},
        )
        self.assertEqual(cross_org_response.status_code, 404)

    def test_exports_have_migration_audit_events_and_no_local_paths(self):
        client = self._client()
        coordinator_token = self._login(client)
        clinician_token = self._login(client, email="clinician@test.authlens.local", role="clinician_reviewer")
        case_id = self._prepare_analyzed_case(client, coordinator_token)
        draft = self._create_verified_draft(client, coordinator_token, case_id)
        approve_response = client.post(
            f"/api/drafts/{draft['id']}/approve",
            headers={"Authorization": f"Bearer {clinician_token}"},
        )
        self.assertEqual(approve_response.status_code, 200, approve_response.text)

        export_response = client.post(
            f"/api/cases/{case_id}/exports/packet",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(export_response.status_code, 201, export_response.text)
        artifact = export_response.json()
        serialized = str(artifact)
        self.assertNotIn("server/uploads", serialized)
        self.assertNotIn("file_uri", serialized)

        download_response = client.get(
            f"/api/exports/{artifact['id']}/download",
            headers={"Authorization": f"Bearer {coordinator_token}"},
        )
        self.assertEqual(download_response.status_code, 200, download_response.text)

        audit_response = client.get("/api/audit", headers={"Authorization": f"Bearer {self._login(client, email='admin@test.authlens.local', role='admin')}"})
        self.assertEqual(audit_response.status_code, 200, audit_response.text)
        actions = [event["action"] for event in audit_response.json()["events"]]
        self.assertIn("export.created", actions)
        self.assertIn("export.downloaded", actions)

        migration = (self.server_dir / "migrations" / "versions" / "20260618_0003_exports.py").read_text(encoding="utf-8")
        self.assertIn('down_revision: Union[str, Sequence[str], None] = "20260617_0002"', migration)


if __name__ == "__main__":
    unittest.main()
