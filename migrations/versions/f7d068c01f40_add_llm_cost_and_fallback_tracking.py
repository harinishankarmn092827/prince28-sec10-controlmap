"""add llm cost and fallback tracking

Revision ID: f7d068c01f40
Revises: 76956aa5aed9
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7d068c01f40"  # pragma: allowlist secret
down_revision: Union[str, Sequence[str], None] = "76956aa5aed9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add cost, fallback, and prompt-version tracking."""
    op.add_column(
        "llm_calls",
        sa.Column(
            "cost_inr",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "llm_calls",
        sa.Column(
            "fallback_used",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "llm_calls",
        sa.Column(
            "prompt_version",
            sa.String(length=50),
            nullable=False,
            server_default="chat_system_v1",
        ),
    )


def downgrade() -> None:
    """Remove cost, fallback, and prompt-version tracking."""
    op.drop_column("llm_calls", "prompt_version")
    op.drop_column("llm_calls", "fallback_used")
    op.drop_column("llm_calls", "cost_inr")
