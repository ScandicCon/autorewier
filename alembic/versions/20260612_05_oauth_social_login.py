"""Add OAuth social-login fields to users.

Revision ID: 20260612_05
Revises: 20260612_04
Create Date: 2026-06-12 01:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260612_05"
down_revision = "20260612_04"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _has_column("users", "oauth_provider"):
        op.add_column("users", sa.Column("oauth_provider", sa.String(length=32), nullable=True))
    if not _has_column("users", "oauth_id"):
        op.add_column("users", sa.Column("oauth_id", sa.String(length=128), nullable=True))
        op.create_index("ix_users_oauth_id", "users", ["oauth_id"])


def downgrade() -> None:
    try:
        op.drop_index("ix_users_oauth_id", table_name="users")
    except Exception:
        pass
    for col in ("oauth_id", "oauth_provider"):
        try:
            op.drop_column("users", col)
        except Exception:
            pass
