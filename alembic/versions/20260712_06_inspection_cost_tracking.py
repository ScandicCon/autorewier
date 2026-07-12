"""Add per-inspection cost tracking columns.

Revision ID: 20260712_06
Revises: 20260612_05
Create Date: 2026-07-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260712_06"
down_revision = "20260612_05"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    # Идемпотентно (SQLite/Postgres): фактическая себестоимость проверки.
    if not _has_column("inspections", "cost_rub"):
        op.add_column("inspections", sa.Column("cost_rub", sa.Float(), nullable=True))
    if not _has_column("inspections", "cost_breakdown"):
        op.add_column("inspections", sa.Column("cost_breakdown", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _has_column("inspections", "cost_breakdown"):
        op.drop_column("inspections", "cost_breakdown")
    if _has_column("inspections", "cost_rub"):
        op.drop_column("inspections", "cost_rub")
