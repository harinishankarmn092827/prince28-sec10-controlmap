"""Parse downloaded documents into pages with text and structural metadata."""

from __future__ import annotations

import csv
import json
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pymupdf
import trafilatura
import yaml
from bs4 import BeautifulSoup

PDF_TABLE_SIZE_LIMIT = 2 * 1024 * 1024
PAGE_CHARS = 3000
MIN_CHARS_PER_PAGE = 50

TEXT_TYPES = {
    ".txt",
    ".md",
    ".mdx",
    ".markdown",
    ".rst",
    ".adoc",
    ".sgml",
    ".py",
}

DATA_TYPES = {
    ".json",
    ".yaml",
    ".yml",
    ".csv",
    ".xml",
}

SUPPORTED_TYPES = (
    TEXT_TYPES
    | DATA_TYPES
    | {
        ".pdf",
        ".html",
        ".htm",
    }
)


@dataclass
class ParsedPage:
    """One parsed page or logical section of a document."""

    page_no: int
    text: str
    heading_path: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)


@dataclass
class ParsedDocument:
    """Structured result produced by a document parser."""

    filename: str
    parser: str
    pages: list[ParsedPage]
    errors: list[str] = field(default_factory=list)


def clean_text(text: str | None) -> str:
    """Normalize whitespace while preserving paragraph boundaries."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")

    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

    cleaned_lines: list[str] = []
    previous_blank = False

    for line in lines:
        if not line:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
        else:
            cleaned_lines.append(line)
            previous_blank = False

    return "\n".join(cleaned_lines).strip()


def _remove_repeated_lines(pages: list[str]) -> list[str]:
    """Remove lines repeated across many pages, such as headers and footers."""
    if len(pages) < 3:
        return pages

    line_counts: dict[str, int] = {}

    for page_text in pages:
        seen_on_page = {line.strip() for line in page_text.splitlines() if line.strip()}

        for line in seen_on_page:
            line_counts[line] = line_counts.get(line, 0) + 1

    repetition_threshold = max(3, int(len(pages) * 0.6))

    repeated_lines = {
        line for line, count in line_counts.items() if count >= repetition_threshold
    }

    cleaned_pages: list[str] = []

    for page_text in pages:
        lines = [
            line
            for line in page_text.splitlines()
            if line.strip() not in repeated_lines
        ]
        cleaned_pages.append(clean_text("\n".join(lines)))

    return cleaned_pages


def _table_to_markdown(rows: list[list[Any]]) -> str:
    """Convert extracted table rows into a Markdown table."""
    normalized_rows: list[list[str]] = []

    for row in rows:
        normalized_row = [
            clean_text("" if cell is None else str(cell)).replace("|", r"\|")
            for cell in row
        ]
        normalized_rows.append(normalized_row)

    normalized_rows = [row for row in normalized_rows if any(cell for cell in row)]

    if not normalized_rows:
        return ""

    column_count = max(len(row) for row in normalized_rows)

    normalized_rows = [
        row + [""] * (column_count - len(row)) for row in normalized_rows
    ]

    header = normalized_rows[0]
    separator = ["---"] * column_count

    markdown_rows = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]

    for row in normalized_rows[1:]:
        markdown_rows.append("| " + " | ".join(row) + " |")

    return "\n".join(markdown_rows)


def _extract_pdf(file_path: Path) -> ParsedDocument:
    """Extract text, headings, and tables from a PDF using PyMuPDF."""
    page_texts: list[str] = []
    page_tables: list[list[str]] = []
    page_headings: list[list[str]] = []

    with pymupdf.open(file_path) as document:
        for page in document:
            text = clean_text(page.get_text("text", sort=True))
            page_texts.append(text)

            tables: list[str] = []

            try:
                table_finder = page.find_tables()

                for table in table_finder.tables:
                    markdown = _table_to_markdown(table.extract())

                    if markdown:
                        tables.append(markdown)
            except Exception:
                # Some PDFs contain malformed or unsupported table layouts.
                # Text extraction should still succeed when possible.
                pass

            page_tables.append(tables)

            headings: list[str] = []

            try:
                page_dict = page.get_text("dict")

                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue

                    for line in block.get("lines", []):
                        spans = line.get("spans", [])
                        line_text = "".join(
                            span.get("text", "") for span in spans
                        ).strip()

                        if not line_text:
                            continue

                        font_size = max(
                            (float(span.get("size", 0)) for span in spans),
                            default=0.0,
                        )

                        is_bold = any(
                            "bold" in str(span.get("font", "")).lower()
                            for span in spans
                        )

                        if len(line_text) <= 180 and (
                            font_size >= 14 or (is_bold and len(line_text) <= 100)
                        ):
                            if line_text not in headings:
                                headings.append(line_text)
            except Exception:
                # Heading detection is best-effort.
                pass

            page_headings.append(headings)

    # FIX: accept short text when at least one page has extractable content.
    # Only reject PDFs when every page contains empty or whitespace-only text.
    if not any(page_text.strip() for page_text in page_texts):
        raise ValueError("no_text_layer: PDF contains no extractable text.")

    page_texts = _remove_repeated_lines(page_texts)

    pages: list[ParsedPage] = []
    current_path: list[str] = []

    for index, page_text in enumerate(page_texts):
        headings = page_headings[index]

        if headings:
            current_path = headings[-3:]

        pages.append(
            ParsedPage(
                page_no=index + 1,
                text=page_text,
                heading_path=current_path.copy(),
                tables=page_tables[index],
                headings=headings,
            )
        )

    return ParsedDocument(
        filename=file_path.name,
        parser="pymupdf",
        pages=pages,
    )


def _html_table_to_markdown(table: Any) -> str:
    """Convert an HTML table element into Markdown."""
    rows: list[list[str]] = []

    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)

        if not cells:
            cells = row.find_all(["th", "td"])

        rows.append([clean_text(cell.get_text(" ", strip=True)) for cell in cells])

    return _table_to_markdown(rows)


def _extract_html(file_path: Path) -> ParsedDocument:
    """Extract readable HTML text, headings, and tables."""
    raw_html = file_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(raw_html, "html.parser")

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title is not None
        else file_path.stem
    )

    headings: list[str] = []

    for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        heading = clean_text(element.get_text(" ", strip=True))

        if heading:
            headings.append(heading)

    tables = [
        markdown
        for table in soup.find_all("table")
        if (markdown := _html_table_to_markdown(table))
    ]

    extracted_text = trafilatura.extract(
        raw_html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )

    if not extracted_text:
        for element in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            element.decompose()

        extracted_text = soup.get_text("\n", strip=True)

    extracted_text = clean_text(extracted_text)

    if title and title not in extracted_text:
        extracted_text = f"{title}\n\n{extracted_text}".strip()

    if tables:
        extracted_text = (extracted_text + "\n\n" + "\n\n".join(tables)).strip()

    return ParsedDocument(
        filename=file_path.name,
        parser="trafilatura",
        pages=[
            ParsedPage(
                page_no=1,
                text=extracted_text,
                heading_path=headings[-3:],
                tables=tables,
                headings=headings,
            )
        ],
    )


def _flatten_json(value: Any, prefix: str = "") -> list[str]:
    """Flatten nested JSON into readable key-value lines."""
    lines: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            lines.extend(_flatten_json(child, child_prefix))

    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            lines.extend(_flatten_json(child, child_prefix))

    else:
        serialized = json.dumps(value, ensure_ascii=False)
        lines.append(f"{prefix}: {serialized}" if prefix else serialized)

    return lines


def _extract_json(file_path: Path) -> ParsedDocument:
    """Parse a JSON file into readable key-value text."""
    raw_text = file_path.read_text(encoding="utf-8")
    data = json.loads(raw_text)

    text = clean_text("\n".join(_flatten_json(data)))

    return _document_from_text(
        filename=file_path.name,
        parser="json",
        text=text,
    )


def _extract_yaml(file_path: Path) -> ParsedDocument:
    """Parse a YAML file into readable key-value text."""
    raw_text = file_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text)

    text = clean_text("\n".join(_flatten_json(data)))

    return _document_from_text(
        filename=file_path.name,
        parser="yaml",
        text=text,
    )


def _extract_csv(file_path: Path) -> ParsedDocument:
    """Parse CSV rows into readable text and Markdown."""
    with file_path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        rows = list(csv.reader(csv_file))

    markdown = _table_to_markdown(rows)

    text_lines: list[str] = []

    if rows:
        headers = rows[0]

        for row_number, row in enumerate(rows[1:], start=1):
            fields = []

            for index, value in enumerate(row):
                key = (
                    headers[index]
                    if index < len(headers) and headers[index]
                    else f"column_{index + 1}"
                )
                fields.append(f"{key}: {value}")

            text_lines.append(f"Row {row_number}: " + "; ".join(fields))

    text = "\n".join(text_lines)

    if markdown:
        text = f"{text}\n\n{markdown}".strip()

    return ParsedDocument(
        filename=file_path.name,
        parser="csv",
        pages=[
            ParsedPage(
                page_no=1,
                text=clean_text(text),
                tables=[markdown] if markdown else [],
            )
        ],
    )


def _xml_to_data(element: ET.Element) -> Any:
    """Convert an XML element tree into nested Python data."""
    children = list(element)
    text = clean_text(element.text)

    if not children:
        if element.attrib:
            result: dict[str, Any] = {
                f"@{key}": value for key, value in element.attrib.items()
            }

            if text:
                result["#text"] = text

            return result if result else text

        return text

    result: dict[str, Any] = {}

    for key, value in element.attrib.items():
        result[f"@{key}"] = value

    if text:
        result["#text"] = text

    for child in children:
        child_data = _xml_to_data(child)

        if child.tag in result:
            existing = result[child.tag]

            if not isinstance(existing, list):
                result[child.tag] = [existing]

            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data

    return result


def _extract_xml(file_path: Path) -> ParsedDocument:
    """Parse XML into readable key-value text."""
    tree = ET.parse(file_path)
    root = tree.getroot()

    data = {root.tag: _xml_to_data(root)}
    text = clean_text("\n".join(_flatten_json(data)))

    return _document_from_text(
        filename=file_path.name,
        parser="xml",
        text=text,
    )


def _extract_text(file_path: Path) -> ParsedDocument:
    """Read a plain-text or source-code document."""
    text = file_path.read_text(encoding="utf-8", errors="replace")

    return _document_from_text(
        filename=file_path.name,
        parser="text",
        text=clean_text(text),
    )


def _document_from_text(
    filename: str,
    parser: str,
    text: str,
) -> ParsedDocument:
    """Split text into logical pages while tracking Markdown headings."""
    text = clean_text(text)

    if not text:
        return ParsedDocument(
            filename=filename,
            parser=parser,
            pages=[
                ParsedPage(
                    page_no=1,
                    text="",
                )
            ],
        )

    lines = text.splitlines()
    sections: list[tuple[list[str], list[str]]] = []

    heading_stack: list[str] = []
    current_lines: list[str] = []
    current_headings: list[str] = []

    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)

        if match:
            if current_lines:
                sections.append((current_lines, current_headings.copy()))
                current_lines = []

            level = len(match.group(1))
            heading = clean_text(match.group(2))

            heading_stack = heading_stack[: level - 1]
            heading_stack.append(heading)
            current_headings.append(heading)

        current_lines.append(line)

    if current_lines:
        sections.append((current_lines, current_headings.copy()))

    if not sections:
        sections = [(lines, [])]

    pages: list[ParsedPage] = []
    page_number = 1

    for section_lines, section_headings in sections:
        section_text = clean_text("\n".join(section_lines))

        if not section_text:
            continue

        chunks = [
            section_text[index : index + PAGE_CHARS]
            for index in range(0, len(section_text), PAGE_CHARS)
        ]

        for chunk in chunks:
            pages.append(
                ParsedPage(
                    page_no=page_number,
                    text=clean_text(chunk),
                    heading_path=section_headings[-3:],
                    headings=section_headings.copy(),
                )
            )
            page_number += 1

    if not pages:
        pages.append(ParsedPage(page_no=1, text=text))

    return ParsedDocument(
        filename=filename,
        parser=parser,
        pages=pages,
    )


def parse_document(
    file_path: str | Path,
    pdf_parser: str = "pymupdf",
) -> ParsedDocument:
    """Parse a supported document file into structured pages."""
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_TYPES:
        raise ValueError(f"Unsupported document extension: {extension or '(none)'}")

    if extension == ".pdf":
        if pdf_parser.lower() != "pymupdf":
            raise ValueError(
                f"Unsupported PDF parser: {pdf_parser}. Currently supported: pymupdf."
            )

        return _extract_pdf(path)

    if extension in {".html", ".htm"}:
        return _extract_html(path)

    if extension == ".json":
        return _extract_json(path)

    if extension in {".yaml", ".yml"}:
        return _extract_yaml(path)

    if extension == ".csv":
        return _extract_csv(path)

    if extension == ".xml":
        return _extract_xml(path)

    return _extract_text(path)


def parsed_document_to_dict(
    document: ParsedDocument,
) -> dict[str, Any]:
    """Convert a parsed document into a JSON-serializable dictionary."""
    return asdict(document)
