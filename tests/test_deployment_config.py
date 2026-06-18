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

    def test_circleci_runs_synthetic_eval_gate(self):
        circleci_config = (PROJECT_ROOT / ".circleci" / "config.yml").read_text(encoding="utf-8")

        self.assertIn("Run synthetic eval smoke gate", circleci_config)
        self.assertIn("python server/evals/run_synthetic_eval.py", circleci_config)


if __name__ == "__main__":
    unittest.main()
