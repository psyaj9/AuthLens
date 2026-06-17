import os

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

DEFAULT_MAX_UPLOAD_FILES = 5
DEFAULT_MAX_UPLOAD_MB = 10.0


def get_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def is_production() -> bool:
    return get_environment() == "production"


def _required_production_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"{name} is required in production")
    return value.strip()


def validate_production_config() -> None:
    if not is_production():
        return

    _required_production_env("JWT_SECRET")
    database_url = _required_production_env("DATABASE_URL")
    _required_production_env("ALLOWED_ORIGINS")
    _required_production_env("INTERNAL_API_TOKEN")

    if database_url.strip().lower().startswith("sqlite"):
        raise RuntimeError("DATABASE_URL must use PostgreSQL in production")

    get_allowed_origins()


def get_allowed_origins() -> list[str]:
    configured_origins = os.getenv("ALLOWED_ORIGINS", "")
    origins = [
        origin.strip()
        for origin in configured_origins.split(",")
        if origin.strip()
    ]
    if "*" in origins:
        raise RuntimeError("ALLOWED_ORIGINS cannot include wildcard when credentials are enabled")

    return origins or list(DEFAULT_ALLOWED_ORIGINS)


def get_internal_api_token() -> str | None:
    token = os.getenv("INTERNAL_API_TOKEN")
    if token is None:
        return None

    token = token.strip()
    return token or None


def _parse_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default

    return value if value > 0 else default


def _parse_float_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError:
        return default

    return value if value > 0 else default


def get_max_upload_files() -> int:
    return _parse_int_env("MAX_UPLOAD_FILES", DEFAULT_MAX_UPLOAD_FILES)


def get_max_upload_mb() -> float:
    return _parse_float_env("MAX_UPLOAD_MB", DEFAULT_MAX_UPLOAD_MB)


def get_max_upload_bytes() -> int:
    return int(get_max_upload_mb() * 1024 * 1024)


def format_upload_mb(value: float) -> str:
    return str(int(value)) if value.is_integer() else str(value)
