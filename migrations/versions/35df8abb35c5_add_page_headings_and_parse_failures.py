"""Add page headings and parse failures.

Revision ID: 35df8abb35c5
Revises: e55f581eb0c8
Create Date: 2026-11-24 19:24:34.600048
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers used by Alembic.
revision: str = "35df8abb35c5"
down_revision: Union[str, None] = "e55f581eb0c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply the schema changes."""
    op.create_table(
        "parse_failures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=40), nullable=False),
        sa.Column(
            "detail",
            sa.Text(),
            server_default="",
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )

    op.create_index(
        op.f("ix_parse_failures_reason"),
        "parse_failures",
        ["reason"],
        unique=False,
    )

    op.add_column(
        "pages",
        sa.Column(
            "headings",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Reverse the schema changes."""
    op.drop_column("pages", "headings")

    op.drop_index(
        op.f("ix_parse_failures_reason"),
        table_name="parse_failures",
    )

    op.drop_table("parse_failures")
