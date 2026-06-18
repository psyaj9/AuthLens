import os

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

DEFAULT_MAX_UPLOAD_FILES = 5
DEFAULT_MAX_UPLOAD_MB = 10.0
DEFAULT_AUTH_RATE_LIMIT_MAX_ATTEMPTS = 5
DEFAULT_AUTH_RATE_LIMIT_WINDOW_SECONDS = 300
DEFAULT_MAX_PDF_PAGES = 25
DEFAULT_MAX_EXTRACTED_CHARS = 200_000
DEFAULT_MAX_DOCUMENT_CHUNKS = 500
PRODUCTION_PASSWORD_RESET_DELIVERY_MODES = {"email", "external"}
TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
FALSY_ENV_VALUES = {"0", "false", "no", "off"}


def get_environment() -> str:
    return os.getenv("ENVIRONMENT", "development").strip().lower() or "development"


def is_production() -> bool:
    return get_environment() == "production"


def _parse_bool_env(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in TRUTHY_ENV_VALUES:
        return True
    if normalized in FALSY_ENV_VALUES:
        return False
    return None


def legacy_qa_enabled() -> bool:
    configured = _parse_bool_env("ENABLE_LEGACY_QA")
    if configured is not None:
        return configured
    return not is_production()


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


def get_password_reset_delivery_mode() -> str:
    return os.getenv("PASSWORD_RESET_DELIVERY_MODE", "").strip().lower()


def _has_nonblank_env(name: str) -> bool:
    value = os.getenv(name)
    return value is not None and bool(value.strip())


def _has_positive_int_env(name: str) -> bool:
    try:
        return int(os.getenv(name, "")) > 0
    except ValueError:
        return False


def password_reset_delivery_configured() -> bool:
    if not is_production():
        return True
    mode = get_password_reset_delivery_mode()
    if mode == "email":
        return (
            _has_nonblank_env("PASSWORD_RESET_PUBLIC_BASE_URL")
            and _has_nonblank_env("PASSWORD_RESET_SMTP_HOST")
            and _has_positive_int_env("PASSWORD_RESET_SMTP_PORT")
            and _has_nonblank_env("PASSWORD_RESET_SMTP_USERNAME")
            and _has_nonblank_env("PASSWORD_RESET_SMTP_PASSWORD")
            and _has_nonblank_env("PASSWORD_RESET_EMAIL_FROM")
        )
    if mode == "external":
        return (
            _has_nonblank_env("PASSWORD_RESET_PUBLIC_BASE_URL")
            and _has_nonblank_env("PASSWORD_RESET_EXTERNAL_WEBHOOK_URL")
            and _has_nonblank_env("PASSWORD_RESET_EXTERNAL_WEBHOOK_TOKEN")
        )
    return False


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


def get_auth_rate_limit_max_attempts() -> int:
    return _parse_int_env("AUTH_RATE_LIMIT_MAX_ATTEMPTS", DEFAULT_AUTH_RATE_LIMIT_MAX_ATTEMPTS)


def get_auth_rate_limit_window_seconds() -> int:
    return _parse_int_env("AUTH_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_AUTH_RATE_LIMIT_WINDOW_SECONDS)


def get_max_pdf_pages() -> int:
    return _parse_int_env("MAX_PDF_PAGES", DEFAULT_MAX_PDF_PAGES)


def get_max_extracted_chars() -> int:
    return _parse_int_env("MAX_EXTRACTED_CHARS", DEFAULT_MAX_EXTRACTED_CHARS)


def get_max_document_chunks() -> int:
    return _parse_int_env("MAX_DOCUMENT_CHUNKS", DEFAULT_MAX_DOCUMENT_CHUNKS)
