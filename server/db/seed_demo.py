from sqlalchemy import select

from db.session import SessionLocal
from models.priorauth import Organization, OrganizationMembership, User
from modules.auth import hash_password


DEMO_ORG_ID = "org_demo_spine"
DEMO_PASSWORD = "demo-password"
DEMO_USERS = [
    ("admin@demo.authlens.test", "Demo Admin", "admin"),
    ("coordinator@demo.authlens.test", "Demo Coordinator", "coordinator"),
    ("clinician@demo.authlens.test", "Demo Clinician", "clinician_reviewer"),
    ("viewer@demo.authlens.test", "Demo Viewer", "viewer"),
]


def seed_demo_data() -> None:
    with SessionLocal() as db:
        org = db.get(Organization, DEMO_ORG_ID)
        if org is None:
            org = Organization(id=DEMO_ORG_ID, name="Demo Spine Clinic", plan="demo")
            db.add(org)

        for email, name, role in DEMO_USERS:
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    name=name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    is_active=True,
                )
                db.add(user)
                db.flush()

            membership = db.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.user_id == user.id,
                    OrganizationMembership.organization_id == org.id,
                )
            )
            if membership is None:
                db.add(
                    OrganizationMembership(
                        user_id=user.id,
                        organization_id=org.id,
                        role=role,
                    )
                )
            else:
                membership.role = role

        db.commit()
