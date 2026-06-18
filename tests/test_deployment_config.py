import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_backend_requirements_include_postgres_driver(self):
        requirements = (PROJECT_ROOT / "server" / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("psycopg2-binary", requirements)

    def test_backend_requirements_include_direct_groq_sdk_dependency(self):
        requirements = (PROJECT_ROOT / "server" / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("groq", requirements.splitlines())

    def test_render_start_command_runs_migrations_before_uvicorn(self):
        render_yaml = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
        expected_start = "python -m alembic -c ../alembic.ini upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"

        self.assertIn(f"startCommand: {expected_start}", render_yaml)
        self.assertLess(render_yaml.index("alembic"), render_yaml.index("uvicorn main:app"))

    def test_readme_matches_render_start_command(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        expected_start = "`python -m alembic -c ../alembic.ini upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`"

        self.assertIn(expected_start, readme)

    def test_password_reset_delivery_mode_is_documented_for_production(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")
        render_yaml = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")

        self.assertIn("PASSWORD_RESET_DELIVERY_MODE", readme)
        self.assertIn("PASSWORD_RESET_DELIVERY_MODE=", env_example)
        self.assertIn("PASSWORD_RESET_DELIVERY_MODE", render_yaml)
        self.assertIn("email", readme)
        self.assertIn("external", readme)
        for variable in [
            "PASSWORD_RESET_PUBLIC_BASE_URL",
            "PASSWORD_RESET_SMTP_HOST",
            "PASSWORD_RESET_SMTP_PORT",
            "PASSWORD_RESET_SMTP_USERNAME",
            "PASSWORD_RESET_SMTP_PASSWORD",
            "PASSWORD_RESET_EMAIL_FROM",
            "PASSWORD_RESET_SMTP_USE_TLS",
            "PASSWORD_RESET_EXTERNAL_WEBHOOK_URL",
            "PASSWORD_RESET_EXTERNAL_WEBHOOK_TOKEN",
        ]:
            self.assertIn(variable, readme)
            self.assertIn(f"{variable}=", env_example)
            self.assertIn(variable, render_yaml)

    def test_circleci_runs_synthetic_eval_gate(self):
        circleci_config = (PROJECT_ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")
        backend_job = circleci_config[
            circleci_config.index("  backend-test:") : circleci_config.index("\n  client-test-build:")
        ]
        eval_step = (
            "      - run:\n"
            "          name: Run synthetic eval smoke gate\n"
            "          command: python server/evals/run_synthetic_eval.py"
        )

        self.assertIn(eval_step, backend_job)
        self.assertLess(backend_job.index("name: Run backend unit tests"), backend_job.index(eval_step))
        self.assertLess(backend_job.index(eval_step), backend_job.index("name: Validate Alembic migrations"))

    def test_circleci_runs_backend_dependency_audit(self):
        circleci_config = (PROJECT_ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")
        backend_job = circleci_config[
            circleci_config.index("  backend-test:") : circleci_config.index("\n  client-test-build:")
        ]
        install_step = (
            "      - run:\n"
            "          name: Install Python audit tooling\n"
            "          command: python -m pip install pip-audit"
        )
        audit_step = (
            "      - run:\n"
            "          name: Audit backend dependencies\n"
            "          command: python -m pip_audit -r server/requirements.txt --strict"
        )

        self.assertIn(install_step, backend_job)
        self.assertIn(audit_step, backend_job)
        self.assertLess(backend_job.index(install_step), backend_job.index(audit_step))
        self.assertLess(backend_job.index(audit_step), backend_job.index("name: Run backend unit tests"))

    def test_circleci_runs_client_high_severity_dependency_audit(self):
        circleci_config = (PROJECT_ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")
        client_job = circleci_config[circleci_config.index("  client-test-build:") :]
        audit_step = (
            "      - run:\n"
            "          name: Audit client dependencies\n"
            "          working_directory: ~/project/client\n"
            "          command: npm audit --audit-level=high"
        )

        self.assertIn(audit_step, client_job)
        self.assertLess(client_job.index("name: Install client dependencies"), client_job.index(audit_step))
        self.assertLess(client_job.index(audit_step), client_job.index("name: Lint client"))

    def test_live_deployment_smoke_gate_is_scripted_and_optional_in_circleci(self):
        self.assertTrue((PROJECT_ROOT / "scripts" / "deployment_smoke.py").exists())
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        circleci_config = (PROJECT_ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")
        backend_job = circleci_config[
            circleci_config.index("  backend-test:") : circleci_config.index("\n  client-test-build:")
        ]

        self.assertIn("AUTHLENS_RENDER_BACKEND_URL", readme)
        self.assertIn("AUTHLENS_VERCEL_CLIENT_URL", readme)
        self.assertIn("name: Run live deployment smoke gate when configured", backend_job)
        self.assertIn("python scripts/deployment_smoke.py", backend_job)
        self.assertIn("Skipping deployment smoke: live deployment URLs are not configured.", backend_job)
        self.assertLess(backend_job.index("name: Validate Alembic migrations"), backend_job.index("name: Run live deployment smoke gate when configured"))


if __name__ == "__main__":
    unittest.main()
