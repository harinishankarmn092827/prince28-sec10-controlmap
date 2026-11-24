"""add parsed page metadata

Revision ID: e55f581eb0c8
Revises: b0dd8cd3d3cd
Create Date: 2026-11-24 15:07:26.223579
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers, used by Alembic.
revision: str = "e55f581eb0c8"
down_revision: Union[str, Sequence[str], None] = "b0dd8cd3d3cd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add parsing metadata columns to the pages table."""
    op.add_column(
        "pages",
        sa.Column(
            "heading_path",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )

    op.add_column(
        "pages",
        sa.Column(
            "tables",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Remove parsing metadata columns from the pages table."""
    op.drop_column("pages", "tables")
    op.drop_column("pages", "heading_path")
