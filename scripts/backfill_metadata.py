import asyncio

from sqlalchemy import select

from app.database.connection import AsyncSessionLocal
from app.database.models import Document, Page
from controlmap.ingest.parse import parse_document
from controlmap.ingest.store import calculate_sha256
from scripts.parse_corpus import discover_documents

FIELDS = ("headings", "heading_path", "tables")


def is_empty(value):
    return value is None or value == [] or value == {}


async def main():
    local_by_hash = {
        calculate_sha256(record["path"]): record["path"]
        for record in discover_documents()
    }

    totals = {
        "matched": 0,
        "eligible": 0,
        "mismatched": 0,
        "pages_to_update": 0,
        **{field: 0 for field in FIELDS},
    }

    async with AsyncSessionLocal() as session:
        documents = (
            await session.scalars(select(Document).order_by(Document.id))
        ).all()

        for document in documents:
            path = local_by_hash.get(document.sha256)

            if path is None:
                continue

            totals["matched"] += 1
            parsed = parse_document(path)

            db_pages = list(
                (
                    await session.scalars(
                        select(Page)
                        .where(Page.doc_id == document.id)
                        .order_by(Page.page_no)
                    )
                ).all()
            )

            if len(db_pages) != len(parsed.pages):
                totals["mismatched"] += 1
                print(
                    f"SKIP: {path.name} | "
                    f"database={len(db_pages)} parsed={len(parsed.pages)}"
                )
                continue

            # Require exact page-number alignment too.
            if any(
                db_page.page_no != parsed_page.page_no
                for db_page, parsed_page in zip(db_pages, parsed.pages)
            ):
                totals["mismatched"] += 1
                print(f"SKIP: page-number mismatch: {path.name}")
                continue

            totals["eligible"] += 1
            document_updates = 0

            for db_page, parsed_page in zip(db_pages, parsed.pages):
                page_has_update = False

                for field in FIELDS:
                    existing_value = getattr(db_page, field)
                    parsed_value = getattr(parsed_page, field)

                    if is_empty(existing_value) and not is_empty(parsed_value):
                        totals[field] += 1
                        page_has_update = True

                if page_has_update:
                    totals["pages_to_update"] += 1
                    document_updates += 1

            print(
                f"CHECK: {path.name} | "
                f"pages={len(db_pages)} | "
                f"pages_with_metadata_to_fill={document_updates}"
            )

    print("\nDRY-RUN SUMMARY")
    print("=" * 45)
    print("Matched documents:", totals["matched"])
    print("Page-count/number mismatches skipped:", totals["mismatched"])
    print("Eligible documents:", totals["eligible"])
    print("Pages with metadata to fill:", totals["pages_to_update"])

    for field in FIELDS:
        print(f"{field} values to fill:", totals[field])

    print("\nNo database records were changed.")


asyncio.run(main())
