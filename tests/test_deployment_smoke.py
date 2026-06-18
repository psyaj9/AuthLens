import json
import unittest
from io import BytesIO
from unittest.mock import patch


class _FakeResponse:
    def __init__(self, body: str, status: int = 200, content_type: str = "application/json"):
        self.body = body.encode("utf-8")
        self.status = status
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class DeploymentSmokeTests(unittest.TestCase):
    def test_smoke_checks_render_backend_vercel_root_and_vercel_backend_binding(self):
        from scripts.deployment_smoke import run_smoke_checks

        requested_urls = []

        def fake_urlopen(request, timeout):
            requested_urls.append(request.full_url)
            if request.full_url == "https://render.example.test/api/health/":
                return _FakeResponse(json.dumps({"status": "ok", "service": "authlens-api"}))
            if request.full_url == "https://vercel.example.test/":
                return _FakeResponse("<html>AuthLens</html>", content_type="text/html")
            if request.full_url == "https://vercel.example.test/api/health":
                return _FakeResponse(
                    json.dumps(
                        {
                            "ok": True,
                            "backendConfigured": True,
                            "backendReachable": True,
                        }
                    )
                )
            raise AssertionError(f"Unexpected URL: {request.full_url}")

        results = run_smoke_checks(
            "https://render.example.test",
            "https://vercel.example.test/",
            opener=fake_urlopen,
        )

        self.assertEqual(
            requested_urls,
            [
                "https://render.example.test/api/health/",
                "https://vercel.example.test/",
                "https://vercel.example.test/api/health",
            ],
        )
        self.assertTrue(all(result.ok for result in results), results)

    def test_smoke_checks_fail_when_client_health_cannot_reach_backend(self):
        from scripts.deployment_smoke import DeploymentSmokeError, run_smoke_checks

        def fake_urlopen(request, timeout):
            if request.full_url == "https://render.example.test/api/health/":
                return _FakeResponse(json.dumps({"status": "ok", "service": "authlens-api"}))
            if request.full_url == "https://vercel.example.test/":
                return _FakeResponse("AuthLens", content_type="text/html")
            return _FakeResponse(
                json.dumps(
                    {
                        "ok": False,
                        "backendConfigured": True,
                        "backendReachable": False,
                    }
                )
            )

        with self.assertRaisesRegex(DeploymentSmokeError, "Vercel client health"):
            run_smoke_checks(
                "https://render.example.test",
                "https://vercel.example.test",
                opener=fake_urlopen,
            )

    def test_load_targets_requires_both_live_urls(self):
        from scripts.deployment_smoke import DeploymentSmokeError, load_targets_from_env

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(DeploymentSmokeError, "AUTHLENS_RENDER_BACKEND_URL"):
                load_targets_from_env()


if __name__ == "__main__":
    unittest.main()
