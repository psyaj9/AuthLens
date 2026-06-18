import time

from fastapi import HTTPException, Request, status

from modules.config import get_auth_rate_limit_max_attempts, get_auth_rate_limit_window_seconds

RATE_LIMIT_MESSAGE = "Too many attempts. Try again later."

_attempts: dict[str, list[float]] = {}
_last_config: tuple[int, int] | None = None


def _client_id(request: Request) -> str:
    if request.client is None:
        return "unknown"
    return request.client.host or "unknown"


def _key(action: str, request: Request, identifier: str = "") -> str:
    normalized_identifier = identifier.strip().lower()
    return f"{action}:{_client_id(request)}:{normalized_identifier}"


def _config() -> tuple[int, int]:
    return get_auth_rate_limit_max_attempts(), get_auth_rate_limit_window_seconds()


def _buckets() -> tuple[int, int, float]:
    global _last_config
    max_attempts, window_seconds = _config()
    if _last_config != (max_attempts, window_seconds):
        _attempts.clear()
        _last_config = (max_attempts, window_seconds)
    return max_attempts, window_seconds, time.monotonic()


def _recent_attempts(key: str, now: float, window_seconds: int) -> list[float]:
    cutoff = now - window_seconds
    recent = [attempt for attempt in _attempts.get(key, []) if attempt >= cutoff]
    _attempts[key] = recent
    return recent


def ensure_not_limited(action: str, request: Request, identifier: str = "") -> None:
    max_attempts, window_seconds, now = _buckets()
    key = _key(action, request, identifier)
    if len(_recent_attempts(key, now, window_seconds)) >= max_attempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=RATE_LIMIT_MESSAGE,
        )


def record_attempt(action: str, request: Request, identifier: str = "") -> None:
    max_attempts, window_seconds, now = _buckets()
    key = _key(action, request, identifier)
    recent = _recent_attempts(key, now, window_seconds)
    if len(recent) < max_attempts:
        recent.append(now)
    _attempts[key] = recent


def record_and_enforce(action: str, request: Request, identifier: str = "") -> None:
    ensure_not_limited(action, request, identifier)
    record_attempt(action, request, identifier)
