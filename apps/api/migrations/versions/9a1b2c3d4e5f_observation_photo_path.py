"""observation.photo_path — локальный путь к дозагруженному фото.

Revision ID: 9a1b2c3d4e5f
Revises: 5c70c265161b
Create Date: 2026-11-24

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "9a1b2c3d4e5f"
down_revision = "5c70c265161b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Добавить колонку с путём к фото."""
    op.add_column("observations", sa.Column("photo_path", sa.String(length=512), nullable=True))


def downgrade() -> None:
    """Удалить колонку."""
    op.drop_column("observations", "photo_path")
