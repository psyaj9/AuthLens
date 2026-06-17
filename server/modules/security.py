from secrets import compare_digest

from fastapi import Header, HTTPException, status

from modules.config import get_internal_api_token, is_production


def require_internal_token(authorization: str | None = Header(default=None)) -> None:
    token = get_internal_api_token()
    if token is None:
        if is_production():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized",
            )
        return

    if authorization is not None and compare_digest(authorization, f"Bearer {token}"):
        return

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized",
    )
