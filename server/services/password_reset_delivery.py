import json
import os
import smtplib
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage


class PasswordResetDeliveryError(Exception):
    pass


class PasswordResetDeliveryConfigError(PasswordResetDeliveryError):
    pass


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise PasswordResetDeliveryConfigError(f"{name} is required")
    return value.strip()


def _required_int_env(name: str) -> int:
    value = _required_env(name)
    try:
        parsed = int(value)
    except ValueError as exc:
        raise PasswordResetDeliveryConfigError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise PasswordResetDeliveryConfigError(f"{name} must be positive")
    return parsed


def _smtp_tls_enabled() -> bool:
    configured = os.getenv("PASSWORD_RESET_SMTP_USE_TLS", "true").strip().lower()
    return configured not in {"0", "false", "no", "off"}


def build_reset_link(public_base_url: str, raw_token: str) -> str:
    base_url = public_base_url.strip().rstrip("/")
    if not base_url:
        raise PasswordResetDeliveryConfigError("PASSWORD_RESET_PUBLIC_BASE_URL is required")
    query = urllib.parse.urlencode({"reset_token": raw_token})
    return f"{base_url}/?{query}"


def deliver_password_reset_email(email: str, reset_link: str) -> None:
    host = _required_env("PASSWORD_RESET_SMTP_HOST")
    port = _required_int_env("PASSWORD_RESET_SMTP_PORT")
    username = _required_env("PASSWORD_RESET_SMTP_USERNAME")
    password = _required_env("PASSWORD_RESET_SMTP_PASSWORD")
    sender = _required_env("PASSWORD_RESET_EMAIL_FROM")

    message = EmailMessage()
    message["Subject"] = "Reset your AuthLens password"
    message["From"] = sender
    message["To"] = email
    message.set_content(
        "A password reset was requested for your AuthLens account.\n\n"
        f"Open this link to reset your password: {reset_link}\n\n"
        "If you did not request this reset, ignore this email."
    )

    try:
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            if _smtp_tls_enabled():
                smtp.starttls()
            smtp.login(username, password)
            smtp.send_message(message)
    except PasswordResetDeliveryConfigError:
        raise
    except Exception as exc:
        raise PasswordResetDeliveryError("Unable to send password reset email") from exc


def deliver_password_reset_external(
    email: str,
    reset_link: str,
    user_id: str,
    organization_id: str,
    expires_in_minutes: int,
) -> None:
    webhook_url = _required_env("PASSWORD_RESET_EXTERNAL_WEBHOOK_URL")
    webhook_token = _required_env("PASSWORD_RESET_EXTERNAL_WEBHOOK_TOKEN")
    payload = {
        "email": email,
        "reset_link": reset_link,
        "user_id": user_id,
        "organization_id": organization_id,
        "expires_in_minutes": expires_in_minutes,
    }
    request = urllib.request.Request(
        webhook_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {webhook_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            if response.status >= 400:
                raise PasswordResetDeliveryError("Password reset handoff was rejected")
    except PasswordResetDeliveryConfigError:
        raise
    except urllib.error.HTTPError as exc:
        raise PasswordResetDeliveryError("Password reset handoff was rejected") from exc
    except urllib.error.URLError as exc:
        raise PasswordResetDeliveryError("Unable to reach password reset handoff endpoint") from exc


def deliver_password_reset(
    mode: str,
    email: str,
    raw_token: str,
    user_id: str,
    organization_id: str,
    expires_in_minutes: int,
) -> None:
    reset_link = build_reset_link(_required_env("PASSWORD_RESET_PUBLIC_BASE_URL"), raw_token)
    if mode == "email":
        deliver_password_reset_email(email, reset_link)
        return
    if mode == "external":
        deliver_password_reset_external(email, reset_link, user_id, organization_id, expires_in_minutes)
        return
    raise PasswordResetDeliveryConfigError("Unsupported password reset delivery mode")
