import asyncio
import re

from sqlalchemy import select

from app.database.connection import AsyncSessionLocal
from app.database.models import Document, Page
from controlmap.ingest.parse import parse_document
from controlmap.ingest.store import calculate_sha256
from scripts.parse_corpus import discover_documents


def normalize(text):
    return re.sub(r"\s+", " ", text or "").strip()


def is_empty(value):
    return value is None or value == [] or value == {}


async def main():
    local_by_hash = {
        calculate_sha256(record["path"]): record["path"]
        for record in discover_documents()
    }

    totals = {
        "matched_documents": 0,
        "page_count_mismatches": 0,
        "text_matches": 0,
        "text_differences": 0,
        "pages_with_metadata_candidates": 0,
        "headings": 0,
        "heading_path": 0,
        "tables": 0,
    }

    async with AsyncSessionLocal() as session:
        documents = (
            await session.scalars(select(Document).order_by(Document.id))
        ).all()

        for document in documents:
            path = local_by_hash.get(document.sha256)

            if path is None:
                continue

            totals["matched_documents"] += 1
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
                totals["page_count_mismatches"] += 1
                print(f"SKIP PAGE COUNT: {path.name}")
                continue

            if any(
                db.page_no != parsed_page.page_no
                for db, parsed_page in zip(db_pages, parsed.pages)
            ):
                totals["page_count_mismatches"] += 1
                print(f"SKIP PAGE NUMBERS: {path.name}")
                continue

            matched_pages = 0
            differing_pages = 0
            candidate_pages = 0

            for db, parsed_page in zip(db_pages, parsed.pages):
                if normalize(db.text) != normalize(parsed_page.text):
                    differing_pages += 1
                    totals["text_differences"] += 1
                    continue

                matched_pages += 1
                totals["text_matches"] += 1

                page_has_candidate = False

                for field in ("headings", "heading_path", "tables"):
                    if is_empty(getattr(db, field)) and not is_empty(
                        getattr(parsed_page, field)
                    ):
                        totals[field] += 1
                        page_has_candidate = True

                if page_has_candidate:
                    candidate_pages += 1
                    totals["pages_with_metadata_candidates"] += 1

            print(
                f"\n{path.name}\n"
                f"  Text matches: {matched_pages}/{len(db_pages)}\n"
                f"  Text differs: {differing_pages}\n"
                f"  Pages with metadata candidates: {candidate_pages}"
            )

    print("\nCONTENT VALIDATION SUMMARY")
    print("=" * 45)
    for key, value in totals.items():
        print(f"{key}: {value}")

    print("\nREAD-ONLY: no database changes were made.")


asyncio.run(main())
