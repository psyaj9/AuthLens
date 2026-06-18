from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_URL_ENV = "AUTHLENS_RENDER_BACKEND_URL"
CLIENT_URL_ENV = "AUTHLENS_VERCEL_CLIENT_URL"
DEFAULT_TIMEOUT_SECONDS = 15


class DeploymentSmokeError(RuntimeError):
    pass


@dataclass(frozen=True)
class SmokeResult:
    name: str
    url: str
    ok: bool
    detail: str


Opener = Callable[[Request, int], object]


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _fetch_text(opener: Opener, url: str, timeout: int) -> tuple[int, str]:
    request = Request(url, headers={"User-Agent": "AuthLens deployment smoke"})
    try:
        with opener(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            body = response.read().decode("utf-8", errors="replace")
            return status, body
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except URLError as exc:
        raise DeploymentSmokeError(f"Unable to reach {url}: {exc.reason}") from exc


def _fetch_json(opener: Opener, url: str, timeout: int) -> tuple[int, dict]:
    status, body = _fetch_text(opener, url, timeout)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise DeploymentSmokeError(f"{url} did not return JSON") from exc
    if not isinstance(payload, dict):
        raise DeploymentSmokeError(f"{url} returned unexpected JSON")
    return status, payload


def _require(condition: bool, result: SmokeResult) -> SmokeResult:
    if not condition:
        raise DeploymentSmokeError(f"{result.name} failed: {result.detail}")
    return result


def run_smoke_checks(
    backend_url: str,
    client_url: str,
    *,
    opener: Opener = urlopen,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> list[SmokeResult]:
    results: list[SmokeResult] = []

    backend_health_url = _join_url(backend_url, "/api/health/")
    backend_status, backend_payload = _fetch_json(opener, backend_health_url, timeout)
    results.append(
        _require(
            backend_status == 200
            and backend_payload.get("status") == "ok"
            and backend_payload.get("service") == "authlens-api",
            SmokeResult(
                "Render backend health",
                backend_health_url,
                False,
                f"status={backend_status}, payload={backend_payload}",
            ),
        )
    )

    client_root_url = _join_url(client_url, "/")
    client_status, client_body = _fetch_text(opener, client_root_url, timeout)
    results.append(
        _require(
            client_status == 200 and bool(client_body.strip()),
            SmokeResult(
                "Vercel client root",
                client_root_url,
                False,
                f"status={client_status}, body_length={len(client_body)}",
            ),
        )
    )

    client_health_url = _join_url(client_url, "/api/health")
    client_health_status, client_health_payload = _fetch_json(opener, client_health_url, timeout)
    results.append(
        _require(
            client_health_status == 200
            and client_health_payload.get("ok") is True
            and client_health_payload.get("backendConfigured") is True
            and client_health_payload.get("backendReachable") is True,
            SmokeResult(
                "Vercel client health",
                client_health_url,
                False,
                f"status={client_health_status}, payload={client_health_payload}",
            ),
        )
    )

    return [SmokeResult(result.name, result.url, True, "ok") for result in results]


def load_targets_from_env() -> tuple[str, str]:
    backend_url = os.getenv(BACKEND_URL_ENV, "").strip()
    client_url = os.getenv(CLIENT_URL_ENV, "").strip()
    missing = [name for name, value in [(BACKEND_URL_ENV, backend_url), (CLIENT_URL_ENV, client_url)] if not value]
    if missing:
        raise DeploymentSmokeError(
            f"Missing deployment smoke URL(s): {', '.join(missing)}"
        )
    return backend_url, client_url


def main() -> int:
    try:
        backend_url, client_url = load_targets_from_env()
        results = run_smoke_checks(backend_url, client_url)
    except DeploymentSmokeError as exc:
        print(f"Deployment smoke failed: {exc}", file=sys.stderr)
        return 1

    for result in results:
        print(f"[ok] {result.name}: {result.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
