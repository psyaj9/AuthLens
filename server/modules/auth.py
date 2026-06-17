import base64
import hashlib
import hmac
import json
import os
from datetime import UTC, datetime, timedelta
from secrets import compare_digest, token_urlsafe
from typing import Any

from fastapi import HTTPException, status

from modules.config import is_production


JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 8 * 60
PASSWORD_ITERATIONS = 120_000


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def get_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    if secret and secret.strip():
        return secret.strip()
    if is_production():
        raise RuntimeError("JWT_SECRET is required in production")
    return "authlens-local-demo-secret"


def hash_password(password: str) -> str:
    salt = token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${_b64encode(digest)}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
    except ValueError:
        return False

    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    return compare_digest(_b64encode(actual), expected)


def create_access_token(
    *,
    user_id: str,
    organization_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    now = datetime.now(UTC)
    expires_at = now + (expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES))
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "sub": user_id,
        "org": organization_id,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    signing_input = ".".join(
        [
            _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(
        get_jwt_secret().encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any]:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        header_text, payload_text, signature_text = token.split(".", 2)
        signing_input = f"{header_text}.{payload_text}"
        expected_signature = hmac.new(
            get_jwt_secret().encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not compare_digest(_b64encode(expected_signature), signature_text):
            raise credentials_error
        payload = json.loads(_b64decode(payload_text))
        expires_at = int(payload["exp"])
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise credentials_error from exc

    if datetime.now(UTC).timestamp() >= expires_at:
        raise credentials_error
    return payload
