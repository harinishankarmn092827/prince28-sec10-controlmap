"""Create documents and pages tables.

Revision ID: 59a81978a18b
Revises: a1b2c3d4e5f6
Create Date: 2026-11-18 13:32:56.835315
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Revision identifiers
revision: str = "59a81978a18b"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade database schema safely."""

    # 1. Create pages table
    op.create_table(
        "pages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("doc_id", sa.Integer(), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["doc_id"],
            ["documents.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "doc_id",
            "page_no",
            name="uq_document_page",
        ),
    )

    op.create_index(
        "ix_pages_doc_id",
        "pages",
        ["doc_id"],
        unique=False,
    )

    # 2. Add new columns as nullable initially
    op.add_column(
        "documents",
        sa.Column("source_url", sa.Text(), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("doc_type", sa.String(length=100), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column("published_on", sa.Date(), nullable=True),
    )

    op.add_column(
        "documents",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # 3. Copy existing document content into pages
    op.execute(
        """
        INSERT INTO pages (doc_id, page_no, text)
        SELECT id, 1, content
        FROM documents
        WHERE content IS NOT NULL
        """
    )

    # 4. Populate new columns for existing documents
    op.execute(
        """
        UPDATE documents
        SET doc_type = 'legacy_import',
            metadata = '{}'::jsonb
        """
    )

    # 5. Make required columns non-nullable
    op.alter_column(
        "documents",
        "doc_type",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    op.alter_column(
        "documents",
        "metadata",
        existing_type=postgresql.JSONB(),
        nullable=False,
    )

    # 6. Increase title length
    op.alter_column(
        "documents",
        "title",
        existing_type=sa.VARCHAR(length=255),
        type_=sa.String(length=500),
        existing_nullable=False,
    )

    # 7. Remove old unique constraint
    op.drop_constraint(
        op.f("documents_sha256_key"),
        "documents",
        type_="unique",
    )

    # 8. Remove old content column only after copying its data
    op.drop_column("documents", "content")


def downgrade() -> None:
    """Restore the previous database schema."""

    # 1. Restore content column
    op.add_column(
        "documents",
        sa.Column("content", sa.Text(), nullable=True),
    )

    # 2. Restore content from pages
    op.execute(
        """
        UPDATE documents AS d
        SET content = COALESCE(
            (
                SELECT p.text
                FROM pages AS p
                WHERE p.doc_id = d.id
                  AND p.page_no = 1
            ),
            ''
        )
        """
    )

    op.alter_column(
        "documents",
        "content",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 3. Restore original title length
    op.alter_column(
        "documents",
        "title",
        existing_type=sa.String(length=500),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )

    # 4. Restore original unique constraint
    op.create_unique_constraint(
        op.f("documents_sha256_key"),
        "documents",
        ["sha256"],
    )

    # 5. Remove newly added columns
    op.drop_column("documents", "metadata")
    op.drop_column("documents", "published_on")
    op.drop_column("documents", "doc_type")
    op.drop_column("documents", "source_url")

    # 6. Remove pages table
    op.drop_index(
        "ix_pages_doc_id",
        table_name="pages",
    )

    op.drop_table("pages")
