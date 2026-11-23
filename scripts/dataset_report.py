"""Generate dataset inventory and capacity reports for ControlMap."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MANIFEST = DATA_DIR / "manifest.jsonl"
SOURCES = DATA_DIR / "sources.csv"

DATASET_REPORT = ROOT / "DATASET.md"
CAPACITY_REPORT = ROOT / "docs" / "CAPACITY.md"
NOTES_FILE = ROOT / "NOTES.md"

START_MARKER = "<!-- generated:start -->"
END_MARKER = "<!-- generated:end -->"

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_PRICE_PER_MILLION = 0.02
EMBEDDING_DIMENSIONS = 1536
FLOAT_BYTES = 4
CHUNK_TOKENS = 800
CHUNK_OVERLAP = 100


def read_manifest() -> list[dict]:
    """Read JSON Lines manifest records."""
    if not MANIFEST.exists():
        raise FileNotFoundError(f"Manifest not found: {MANIFEST}")

    records = []

    for line_number, line in enumerate(
        MANIFEST.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid manifest JSON on line {line_number}") from exc

    return records


def read_sources() -> list[dict]:
    """Read the configured source inventory."""
    if not SOURCES.exists():
        return []

    with SOURCES.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        return list(csv.DictReader(file))


def extract_text(path: Path) -> str:
    """Extract approximate text from supported document formats."""
    suffix = path.suffix.lower()

    try:
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)

        if suffix == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            return json.dumps(data, ensure_ascii=False)

        if suffix in {".html", ".htm"}:
            html = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            html = re.sub(
                r"<(script|style)\b[^>]*>.*?</\1>",
                " ",
                html,
                flags=re.IGNORECASE | re.DOTALL,
            )
            return re.sub(r"<[^>]+>", " ", html)

        return ""

    except Exception as exc:
        print(f"Warning: Could not extract text from {path}: {exc}")
        return ""


def update_generated_section(
    path: Path,
    generated_content: str,
) -> None:
    """Update generated content while preserving manual content."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8-sig")
    else:
        existing = ""

    has_start = START_MARKER in existing
    has_end = END_MARKER in existing

    if has_start != has_end:
        raise ValueError(
            f"{path} contains an incomplete generated section. "
            "Please repair its markers before regenerating."
        )

    if has_start and has_end:
        before, remainder = existing.split(START_MARKER, 1)
        _, after = remainder.split(END_MARKER, 1)

        updated = (
            before
            + START_MARKER
            + "\n"
            + generated_content.strip()
            + "\n"
            + END_MARKER
            + after
        )

    elif existing.strip():
        updated = (
            existing.rstrip()
            + "\n\n"
            + START_MARKER
            + "\n"
            + generated_content.strip()
            + "\n"
            + END_MARKER
            + "\n"
        )

    else:
        updated = (
            START_MARKER + "\n" + generated_content.strip() + "\n" + END_MARKER + "\n"
        )

    path.write_text(updated, encoding="utf-8")


def human_size(size: int) -> str:
    """Format bytes as a readable size."""
    value = float(size)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.2f} {unit}"
        value /= 1024

    return f"{value:.2f} TB"


def build_dataset_report(
    records: list[dict],
    sources: list[dict],
) -> tuple[str, dict]:
    """Build the dataset report and return measured statistics."""
    formats = Counter()
    source_counts = Counter()
    status_counts = Counter()

    total_bytes = 0
    pdf_pages = 0
    missing_files = []
    file_rows = []
    extracted_characters = 0

    for record in records:
        status_counts[record.get("status", "unknown")] += 1

        relative_path = record.get("path", "")
        path = ROOT / relative_path if relative_path else None

        extension = (
            path.suffix.lower()
            if path is not None
            else Path(urlparse(record.get("url", "")).path).suffix.lower()
        )

        size = 0

        if path is not None and path.is_file():
            size = path.stat().st_size
            total_bytes += size

            text = extract_text(path)
            extracted_characters += len(text)

            if extension == ".pdf":
                try:
                    pdf_pages += len(PdfReader(str(path)).pages)
                except Exception as exc:
                    print(f"Warning: PDF page count failed for {path}: {exc}")

        else:
            missing_files.append(relative_path or record.get("url", "unknown"))

        formats[extension or "(no extension)"] += 1
        source_counts[record.get("source", "unknown")] += 1

        file_rows.append(
            {
                "source": record.get("source", "unknown"),
                "title": record.get("title", "Untitled"),
                "format": extension or "(unknown)",
                "size": size,
                "status": record.get("status", "unknown"),
            }
        )

    configured_by_source = Counter(row.get("source", "unknown") for row in sources)

    lines = [
        "# ControlMap Dataset Inventory",
        "",
        "This report is generated by `scripts/dataset_report.py`.",
        "",
        "## Collection summary",
        "",
        f"- Manifest records: **{len(records)}**",
        f"- Configured source rows: **{len(sources)}**",
        (f"- Total size of available manifest files: **{human_size(total_bytes)}**"),
        f"- PDF pages across readable PDFs: **{pdf_pages}**",
        (f"- Approximate extracted characters: **{extracted_characters:,}**"),
        (f"- Missing files referenced by the manifest: **{len(missing_files)}**"),
        "",
        "### Download statuses",
        "",
        "| Status | Records |",
        "|---|---:|",
    ]

    for status, count in sorted(status_counts.items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "### File formats",
            "",
            "| Format | Manifest records |",
            "|---|---:|",
        ]
    )

    for extension, count in sorted(formats.items()):
        lines.append(f"| `{extension}` | {count} |")

    lines.extend(
        [
            "",
            "### Source coverage",
            "",
            ("| Source | Configured URLs | Manifest records |"),
            "|---|---:|---:|",
        ]
    )

    all_sources = set(configured_by_source) | set(source_counts)

    for source in sorted(all_sources):
        lines.append(
            f"| {source} | {configured_by_source[source]} | {source_counts[source]} |"
        )

    lines.extend(
        [
            "",
            "### Downloaded file inventory",
            "",
            "| Source | Title | Format | Size | Status |",
            "|---|---|---|---:|---|",
        ]
    )

    for item in file_rows:
        title = item["title"].replace("|", "\\|")

        lines.append(
            f"| {item['source']} | {title} "
            f"| `{item['format']}` "
            f"| {human_size(item['size'])} "
            f"| {item['status']} |"
        )

    if missing_files:
        lines.extend(
            [
                "",
                "### Missing files",
                "",
            ]
        )
        lines.extend(f"- `{path}`" for path in missing_files)

    lines.extend(
        [
            "",
            "## Source and licensing notes",
            "",
            (
                "- **NIST:** NIST publications are generally public "
                "domain in the United States. Retain attribution "
                "and check for third-party material."
            ),
            (
                "- **SEBI:** Public accessibility does not establish "
                "unrestricted reuse rights. Verify applicable terms "
                "before redistributing documents or extracted content."
            ),
            (
                "- **OSCAL:** Preserve original source URLs and file "
                "hashes to support traceability."
            ),
            (
                "- Keep source documents separate from reviewed "
                "cross-framework mappings and AI-generated explanations."
            ),
            "",
            "## Known limitations",
            "",
            (
                "- A successful download does not prove that a document "
                "is current or applicable to every regulated entity."
            ),
            (
                "- Previously collected SEBI HTML landing pages may "
                "remain alongside corresponding PDF documents. Treat "
                "them as landing-page snapshots, not additional primary "
                "regulatory publications."
            ),
            (
                "- PDF page counts do not measure the completeness "
                "or accuracy of extracted text."
            ),
            (
                "- Verify source versions, circular dates, entity "
                "applicability, and reviewed mappings before relying "
                "on the results for compliance decisions."
            ),
            "",
            "## Reproducibility",
            "",
            "- Manifest: `data/manifest.jsonl`",
            "- Configured URLs: `data/sources.csv`",
            "- Downloaded files: `data/raw/`",
            "- Regenerate: `uv run python scripts/dataset_report.py`",
        ]
    )

    stats = {
        "record_count": len(records),
        "source_count": len(sources),
        "total_bytes": total_bytes,
        "pdf_pages": pdf_pages,
        "extracted_characters": extracted_characters,
        "missing_files": len(missing_files),
        "formats": formats,
    }

    return "\n".join(lines), stats


def build_capacity_report(stats: dict) -> str:
    """Build a transparent, assumption-based capacity estimate."""
    estimated_tokens = max(
        1,
        round(stats["extracted_characters"] / 4),
    )

    embedding_cost = (estimated_tokens / 1_000_000) * EMBEDDING_PRICE_PER_MILLION

    effective_chunk_size = CHUNK_TOKENS - CHUNK_OVERLAP

    estimated_chunks = max(
        1,
        (estimated_tokens + effective_chunk_size - 1) // effective_chunk_size,
    )

    vector_bytes = estimated_chunks * EMBEDDING_DIMENSIONS * FLOAT_BYTES

    vector_size = human_size(vector_bytes)

    lines = [
        "# ControlMap Capacity Estimate",
        "",
        (
            "This report is generated by `scripts/dataset_report.py`. "
            "These are planning estimates, not measurements of a "
            "completed embedding pipeline."
        ),
        "",
        "## Embedding cost",
        "",
        (f"**Estimated one-time embedding input cost: ${embedding_cost:.6f} USD**"),
        "",
        (
            f"This estimate covers approximately {estimated_tokens:,} "
            f"tokens using `{EMBEDDING_MODEL}` at an assumed rate of "
            "$0.02 per million input tokens."
        ),
        "",
        (
            "The estimate uses extracted characters divided by four. "
            "Actual token counts depend on the tokenizer, cleaning, "
            "chunking, and the text submitted to the embedding API. "
            "Verify pricing before use."
        ),
        "",
        "## PostgreSQL storage",
        "",
        (
            f"The local corpus is approximately "
            f"**{human_size(stats['total_bytes'])}** across "
            f"{stats['record_count']} manifest records."
        ),
        "",
        (f"The estimated extracted text is approximately {estimated_tokens:,} tokens."),
        "",
        (
            f"At {EMBEDDING_DIMENSIONS} dimensions and four bytes "
            f"per vector component, the raw vector payload is "
            f"approximately **{vector_size}** for "
            f"{estimated_chunks:,} chunks."
        ),
        "",
        (
            "This excludes PostgreSQL row overhead, indexes, metadata, "
            "and other database contents."
        ),
        "",
        (
            "Check the current Neon Free plan storage allowance and "
            "actual usage in your Neon dashboard. Compare the measured "
            "database size with the available storage before deciding "
            "whether an upgrade is needed."
        ),
        "",
        "### Measure actual database usage",
        "",
        "Run these queries in your PostgreSQL SQL console:",
        "",
        "```sql",
        ("SELECT pg_size_pretty(pg_database_size(current_database()))"),
        "    AS database_size;",
        "",
        "SELECT",
        "    schemaname,",
        "    relname,",
        "    pg_size_pretty(",
        "        pg_total_relation_size(",
        "            quote_ident(schemaname) || '.' || quote_ident(relname)",
        "        )",
        "    ) AS total_table_size",
        "FROM pg_stat_user_tables",
        "ORDER BY pg_total_relation_size(",
        "    quote_ident(schemaname) || '.' || quote_ident(relname)",
        ") DESC;",
        "```",
        "",
        "## Least-certain estimate",
        "",
        (
            "The least-certain figure is the number of tokens and "
            "chunks that will actually be embedded."
        ),
        "",
        (
            "PDF extraction, repeated headers, document cleaning, "
            "and chunk overlap can change the final count substantially."
        ),
        "",
        (
            "To improve the estimate, extract accepted documents, apply "
            "the intended cleaning and chunking pipeline, count tokens "
            "with the selected model's tokenizer, and record the actual "
            "chunk count before embedding."
        ),
        "",
        "## What changes at 10x corpus size?",
        "",
        (
            "- Embedding cost and raw vector storage should grow "
            "approximately 10x if the document mix, chunking rules, "
            "and embedding dimensions remain unchanged."
        ),
        (
            "- Measure database size, query latency, index build time, "
            "and ingestion throughput; tune indexing or increase "
            "storage capacity if necessary."
        ),
        "",
        "## Assumptions",
        "",
        f"- Chunk size: {CHUNK_TOKENS} tokens.",
        f"- Chunk overlap: {CHUNK_OVERLAP} tokens.",
        f"- Embedding dimensions: {EMBEDDING_DIMENSIONS}.",
        ("- Vector payload: four bytes per dimension, excluding database overhead."),
        f"- Model: `{EMBEDDING_MODEL}`.",
        ("- Assumed price: $0.02 per million input tokens; verify current pricing."),
    ]

    return "\n".join(lines)


def append_d06_notes() -> None:
    """Append D06 notes without replacing existing documentation."""
    if not NOTES_FILE.exists():
        print("NOTES.md not found; skipping D06 notes update.")
        return

    existing = NOTES_FILE.read_text(encoding="utf-8-sig")

    heading = "## D06 — Document Collection Pipeline"

    if heading in existing:
        print("NOTES.md already contains D06; preserving it.")
        return

    section = """
## D06 — Document Collection Pipeline

### Implementation
- Added the asynchronous document fetcher under
  `src/controlmap/ingest/fetch.py`.
- Added `scripts/fetch.py` for URL lists, repositories, sitemaps,
  and manual collection workflows.
- Configured ten source URLs in `data/sources.csv`.
- Added fetcher unit tests and manifest-based download tracking.
- Added retries, concurrency limits, and content-type-aware
  file extension handling.

### Collection results
- The manifest records collected source files.
- The corpus includes NIST OSCAL JSON, NIST PDF publications,
  and SEBI CSCRF PDFs plus previously retained HTML landing pages.
- NIST documents are noted as public domain; SEBI reuse terms
  require verification.
- Generate dataset and capacity reports using
  `uv run python scripts/dataset_report.py`.

### Verification
- Fetcher unit tests: 21 passed in the last recorded run.
- Full unit test suite: 25 passed in the last recorded run.
- Ruff lint passed in the last recorded run.
- PDF signatures and page counts were checked during collection.
- Re-run tests after subsequent code or data changes.
"""

    NOTES_FILE.write_text(
        existing.rstrip() + "\n\n" + section.strip() + "\n",
        encoding="utf-8",
    )

    print("Appended D06 section to NOTES.md.")


def main() -> None:
    """Generate dataset and capacity reports."""
    records = read_manifest()
    sources = read_sources()

    dataset_content, stats = build_dataset_report(records, sources)
    capacity_content = build_capacity_report(stats)

    update_generated_section(DATASET_REPORT, dataset_content)
    update_generated_section(CAPACITY_REPORT, capacity_content)

    append_d06_notes()

    print("\nDataset report generated successfully.")
    print(f"Manifest records: {stats['record_count']}")
    print(f"Configured sources: {stats['source_count']}")
    print(f"Corpus size: {human_size(stats['total_bytes'])}")
    print(f"PDF pages: {stats['pdf_pages']}")
    print(f"Missing files: {stats['missing_files']}")
    print(f"Dataset report: {DATASET_REPORT.relative_to(ROOT)}")
    print(f"Capacity report: {CAPACITY_REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
