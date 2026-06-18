from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user
from models.priorauth import Organization, OrganizationMembership, PasswordResetToken, User
from modules.auth import create_access_token, hash_password, hash_reset_token, verify_password
from modules.config import is_production, password_reset_delivery_configured
from modules.schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    MessageResponse,
    OrganizationSummary,
    RegisterRequest,
    ResetPasswordRequest,
    UserProfile,
)
from services.audit import log_audit_event


router = APIRouter()
RESET_TOKEN_EXPIRE_MINUTES = 60
RESET_MESSAGE = "If an account exists, password reset instructions have been prepared."


def normalize_email(email: str) -> str:
    return email.strip().lower()


def user_profile(user: User, organization: Organization, role: str) -> UserProfile:
    return UserProfile(
        id=user.id,
        email=user.email,
        name=user.name,
        role=role,
        organization=OrganizationSummary(
            id=organization.id,
            name=organization.name,
            plan=organization.plan,
        ),
    )


@router.post("/auth/login", response_model=AuthResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    membership = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id))
    if membership is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    organization = db.get(Organization, membership.organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(
        user_id=user.id,
        organization_id=organization.id,
        role=membership.role,
        token_version=user.token_version,
    )
    log_audit_event(
        db,
        organization_id=organization.id,
        user_id=user.id,
        action="user.login",
        entity_type="user",
        entity_id=user.id,
        metadata={"role": membership.role},
    )
    db.commit()
    return AuthResponse(access_token=token, user=user_profile(user, organization, membership.role))


@router.post("/auth/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = normalize_email(payload.email)
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    organization = Organization(name=payload.organization_name.strip(), plan="self_service")
    user = User(
        email=email,
        name=payload.name.strip(),
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(organization)
    db.add(user)
    db.flush()
    membership = OrganizationMembership(
        user_id=user.id,
        organization_id=organization.id,
        role="admin",
    )
    db.add(membership)
    log_audit_event(
        db,
        organization_id=organization.id,
        user_id=user.id,
        action="user.registered",
        entity_type="user",
        entity_id=user.id,
        metadata={"role": membership.role},
    )
    token = create_access_token(
        user_id=user.id,
        organization_id=organization.id,
        role=membership.role,
        token_version=user.token_version,
    )
    db.commit()
    db.refresh(user)
    db.refresh(organization)
    return AuthResponse(access_token=token, user=user_profile(user, organization, membership.role))


@router.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
async def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    if is_production() and not password_reset_delivery_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset delivery is not configured",
        )

    reset_token = None
    user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    if user is not None and user.is_active:
        now = datetime.now(UTC)
        existing_tokens = db.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        ).all()
        for existing_token in existing_tokens:
            existing_token.used_at = now

        raw_token = token_urlsafe(32)
        membership = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id))
        token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_token(raw_token),
            expires_at=now + timedelta(minutes=RESET_TOKEN_EXPIRE_MINUTES),
        )
        db.add(token_record)
        if membership is not None:
            log_audit_event(
                db,
                organization_id=membership.organization_id,
                user_id=user.id,
                action="password_reset.requested",
                entity_type="user",
                entity_id=user.id,
            )
        if not is_production():
            reset_token = raw_token
        db.commit()
    return ForgotPasswordResponse(message=RESET_MESSAGE, reset_token=reset_token)


@router.post("/auth/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    token_record = db.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == hash_reset_token(payload.reset_token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
    )
    if token_record is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    user = db.get(User, token_record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")

    membership = db.scalar(select(OrganizationMembership).where(OrganizationMembership.user_id == user.id))
    user.password_hash = hash_password(payload.password)
    user.token_version += 1
    token_record.used_at = now
    remaining_tokens = db.scalars(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.id != token_record.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).all()
    for remaining_token in remaining_tokens:
        remaining_token.used_at = now

    if membership is not None:
        log_audit_event(
            db,
            organization_id=membership.organization_id,
            user_id=user.id,
            action="password_reset.completed",
            entity_type="user",
            entity_id=user.id,
        )
    db.commit()
    return MessageResponse(message="Password reset complete.")


@router.get("/auth/me", response_model=UserProfile)
async def me(current_user: CurrentUser = Depends(get_current_user)):
    return UserProfile(
        id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        role=current_user.role,
        organization=OrganizationSummary(
            id=current_user.organization_id,
            name=current_user.organization_name,
        ),
    )
