"""Add VIN quota counters and report-pack credits.

Revision ID: 20260612_04
Revises: 20260610_03
Create Date: 2026-06-12 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "20260612_04"
down_revision = "20260610_03"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    # Идемпотентно: добавляем только отсутствующие колонки (SQLite/Postgres).
    if not _has_column("users", "vin_reports_this_month"):
        op.add_column(
            "users",
            sa.Column("vin_reports_this_month", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column("users", "report_credits"):
        op.add_column(
            "users",
            sa.Column("report_credits", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column("payments", "product"):
        op.add_column(
            "payments",
            sa.Column("product", sa.String(length=32), nullable=False, server_default="subscription"),
        )
    if not _has_column("payments", "report_credits"):
        op.add_column(
            "payments",
            sa.Column("report_credits", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    for table, col in [
        ("payments", "report_credits"),
        ("payments", "product"),
        ("users", "report_credits"),
        ("users", "vin_reports_this_month"),
    ]:
        try:
            op.drop_column(table, col)
        except Exception:
            pass
