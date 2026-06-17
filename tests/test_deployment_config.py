import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTests(unittest.TestCase):
    def test_backend_requirements_include_postgres_driver(self):
        requirements = (PROJECT_ROOT / "server" / "requirements.txt").read_text(encoding="utf-8")

        self.assertIn("psycopg2-binary", requirements)

    def test_render_start_command_runs_migrations_before_uvicorn(self):
        render_yaml = (PROJECT_ROOT / "render.yaml").read_text(encoding="utf-8")
        expected_start = "python -m alembic -c ../alembic.ini upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT"

        self.assertIn(f"startCommand: {expected_start}", render_yaml)
        self.assertLess(render_yaml.index("alembic"), render_yaml.index("uvicorn main:app"))

    def test_readme_matches_render_start_command(self):
        readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        expected_start = "`python -m alembic -c ../alembic.ini upgrade head && uvicorn main:app --host 0.0.0.0 --port $PORT`"

        self.assertIn(expected_start, readme)


if __name__ == "__main__":
    unittest.main()
