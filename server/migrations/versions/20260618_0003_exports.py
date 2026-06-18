"""add export artifacts

Revision ID: 20260618_0003
Revises: 20260617_0002
Create Date: 2026-06-18 10:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260618_0003"
down_revision: Union[str, Sequence[str], None] = "20260617_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "export_artifacts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("organization_id", sa.String(length=64), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("export_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=False),
        sa.Column("content_markdown", sa.Text(), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["prior_auth_cases.id"]),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_exports_case_type", "export_artifacts", ["case_id", "export_type"], unique=False)
    op.create_index(op.f("ix_export_artifacts_case_id"), "export_artifacts", ["case_id"], unique=False)
    op.create_index(op.f("ix_export_artifacts_created_by_user_id"), "export_artifacts", ["created_by_user_id"], unique=False)
    op.create_index(op.f("ix_export_artifacts_export_type"), "export_artifacts", ["export_type"], unique=False)
    op.create_index(op.f("ix_export_artifacts_organization_id"), "export_artifacts", ["organization_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_export_artifacts_organization_id"), table_name="export_artifacts")
    op.drop_index(op.f("ix_export_artifacts_export_type"), table_name="export_artifacts")
    op.drop_index(op.f("ix_export_artifacts_created_by_user_id"), table_name="export_artifacts")
    op.drop_index(op.f("ix_export_artifacts_case_id"), table_name="export_artifacts")
    op.drop_index("ix_exports_case_type", table_name="export_artifacts")
    op.drop_table("export_artifacts")
