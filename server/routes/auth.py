from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.session import get_db
from dependencies.auth import CurrentUser, get_current_user
from models.priorauth import Organization, OrganizationMembership, User
from modules.auth import create_access_token, verify_password
from modules.schemas import AuthResponse, LoginRequest, OrganizationSummary, UserProfile
from services.audit import log_audit_event


router = APIRouter()


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
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
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
