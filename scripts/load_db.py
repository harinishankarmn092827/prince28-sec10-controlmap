"""Load local text and Markdown documents into PostgreSQL."""

import asyncio
import hashlib
from pathlib import Path

from sqlalchemy import select

from app.database.connection import AsyncSessionLocal
from app.database.models import Document, Page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "documents"

SUPPORTED_EXTENSIONS = {".txt", ".md"}


async def load_document(file_path: Path) -> str:
    """Load one document, avoiding duplicate SHA-256 hashes."""

    content = file_path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    async with AsyncSessionLocal() as session:
        existing = await session.scalar(
            select(Document).where(Document.sha256 == content_hash)
        )

        if existing:
            return f"Skipped duplicate: {file_path.name}"

        document = Document(
            title=file_path.stem,
            source_url=None,
            doc_type=file_path.suffix.lstrip("."),
            published_on=None,
            sha256=content_hash,
            document_metadata={
                "filename": file_path.name,
                "loader": "scripts/load_db.py",
            },
        )

        document.pages.append(
            Page(
                page_no=1,
                text=content,
            )
        )

        session.add(document)
        await session.commit()

    return f"Loaded successfully: {file_path.name}"


async def main() -> None:
    """Load all supported documents from the input directory."""

    if not DOCUMENTS_DIR.exists():
        DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created input folder: {DOCUMENTS_DIR}")
        print("Add .txt or .md documents and run the loader again.")
        return

    files = [
        path
        for path in DOCUMENTS_DIR.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not files:
        print("No .txt or .md documents found.")
        return

    for file_path in files:
        try:
            result = await load_document(file_path)
            print(result)
        except Exception as error:
            print(f"Failed to load {file_path.name}: {error}")


if __name__ == "__main__":
    asyncio.run(main())
