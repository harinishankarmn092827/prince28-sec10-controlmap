"""Import cybersecurity framework control records into PostgreSQL."""

import asyncio
import hashlib
import json
from datetime import date

from sqlalchemy import select

from app.core.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.models import Document, Page


async def import_records() -> None:
    """Import JSON control records without creating duplicates."""

    data_file = settings.data_file

    if not data_file.is_file():
        print(f"JSON file not found: {data_file}")
        return

    with data_file.open(encoding="utf-8") as file:
        records = json.load(file)

    if not isinstance(records, list):
        raise ValueError("Control records must be a JSON list.")

    imported = 0
    skipped = 0

    async with AsyncSessionLocal() as session:
        for record in records:
            record_json = json.dumps(
                record,
                sort_keys=True,
                ensure_ascii=False,
            )

            content_hash = hashlib.sha256(record_json.encode("utf-8")).hexdigest()

            existing = await session.scalar(
                select(Document).where(Document.sha256 == content_hash)
            )

            if existing:
                print(f"Skipped duplicate: {record['control_id']}")
                skipped += 1
                continue

            source_date = date.fromisoformat(record["source_date"])

            metadata = {
                "original_record_id": record["id"],
                "framework": record["framework"],
                "control_id": record["control_id"],
                "function_or_family": record["function_or_family"],
                "applies_to_category": record["applies_to_category"],
                "source_date": record["source_date"],
                "record_type": "framework_control",
            }

            document = Document(
                title=record["title"],
                source_url=None,
                doc_type="control_record",
                published_on=source_date,
                sha256=content_hash,
                document_metadata=metadata,
            )

            page_text = (
                f"Framework: {record['framework']}\n"
                f"Control ID: {record['control_id']}\n"
                f"Title: {record['title']}\n"
                f"Function or Family: {record['function_or_family']}\n"
                f"Applicable Category: {record['applies_to_category']}\n"
                f"Source Date: {record['source_date']}"
            )

            document.pages.append(
                Page(
                    page_no=1,
                    text=page_text,
                )
            )

            session.add(document)
            imported += 1

        await session.commit()

    print("\nImport completed!")
    print(f"Imported records: {imported}")
    print(f"Skipped duplicates: {skipped}")


if __name__ == "__main__":
    asyncio.run(import_records())
