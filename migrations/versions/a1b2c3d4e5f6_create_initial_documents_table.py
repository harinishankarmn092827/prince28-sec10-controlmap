"""Create the initial documents table.

Revision ID: a1b2c3d4e5f6
Revises:
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the original documents table."""

    op.create_table(
        "documents",
        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.UniqueConstraint(
            "sha256",
            name="documents_sha256_key",
        ),
    )


def downgrade() -> None:
    """Remove the initial documents table."""

    op.drop_table("documents")
