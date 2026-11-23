"""Unit tests for the ControlMap document downloader."""

import asyncio
import csv
import hashlib
import json

import httpx
import pytest

from src.controlmap.ingest.fetch import (
    MAX_WAIT,
    DownloadError,
    HostGate,
    Manifest,
    Robots,
    Source,
    _download,
    backoff_delay,
    fetch_all,
    file_stem,
    pick_ext,
    read_sources,
    retry_after_seconds,
    slug,
)

# --------------------------------------------------
# 1. Filename and URL helper tests
# --------------------------------------------------


def test_slug_removes_invalid_characters():
    assert slug("NIST SP 800/53") == "NIST-SP-800-53"


def test_slug_handles_empty_string():
    assert slug("...") == "document"


def test_file_stem_is_stable():
    url = "https://example.com/documents/report.pdf"

    assert file_stem(url) == file_stem(url)


def test_pick_ext_uses_url_extension():
    assert (
        pick_ext(
            "https://example.com/report.pdf",
            "application/octet-stream",
        )
        == ".pdf"
    )


def test_pick_ext_uses_content_type():
    assert (
        pick_ext(
            "https://example.com/download",
            "application/pdf; charset=binary",
        )
        == ".pdf"
    )


# --------------------------------------------------
# 2. Retry handling tests
# --------------------------------------------------


def test_backoff_delay_is_bounded(monkeypatch):
    monkeypatch.setattr(
        "src.controlmap.ingest.fetch.random.uniform",
        lambda _a, _b: 0.5,
    )

    assert backoff_delay(0) == 1.5
    assert backoff_delay(1) == 2.5
    assert backoff_delay(100) == MAX_WAIT


def test_retry_after_numeric_value():
    assert retry_after_seconds("10") == 10.0


def test_retry_after_is_capped():
    assert retry_after_seconds("9999") == MAX_WAIT


def test_retry_after_invalid_value():
    assert retry_after_seconds("not-a-valid-date") is None


# --------------------------------------------------
# 3. CSV source validation tests
# --------------------------------------------------


def test_read_sources_valid_csv(tmp_path):
    csv_path = tmp_path / "sources.csv"

    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["url", "source", "licence", "title"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "url": "https://example.com/report.pdf",
                "source": "example",
                "licence": "Public domain",
                "title": "Example Report",
            }
        )

    sources = read_sources(csv_path)

    assert len(sources) == 1
    assert sources[0] == Source(
        url="https://example.com/report.pdf",
        source="example",
        licence="Public domain",
        title="Example Report",
    )


def test_read_sources_missing_columns(tmp_path):
    csv_path = tmp_path / "sources.csv"
    csv_path.write_text("url,title\nhttps://example.com,Example\n")

    with pytest.raises(ValueError, match="columns"):
        read_sources(csv_path)


def test_read_sources_rejects_invalid_url(tmp_path):
    csv_path = tmp_path / "sources.csv"

    csv_path.write_text(
        "url,source,licence\nftp://example.com/file,example,Public domain\n"
    )

    with pytest.raises(ValueError, match="Invalid HTTP"):
        read_sources(csv_path)


def test_read_sources_requires_source_and_licence(tmp_path):
    csv_path = tmp_path / "sources.csv"

    csv_path.write_text("url,source,licence\nhttps://example.com/file,,\n")

    with pytest.raises(ValueError, match="required"):
        read_sources(csv_path)


# --------------------------------------------------
# 4. Manifest tests
# --------------------------------------------------


def test_manifest_ignores_malformed_lines(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"

    manifest_path.write_text(
        '{"url":"https://example.com/a","status":"failed"}\n'
        "this is not valid JSON\n"
        '{"url":"https://example.com/b","status":"failed"}\n',
        encoding="utf-8",
    )

    manifest = Manifest(manifest_path)

    assert len(manifest.records) == 2
    assert "https://example.com/a" in manifest.records
    assert "https://example.com/b" in manifest.records


def test_manifest_done_requires_existing_file(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    downloaded_file = tmp_path / "data" / "raw" / "report.pdf"

    downloaded_file.parent.mkdir(parents=True)
    downloaded_file.write_text("test document")

    manifest = Manifest(manifest_path)

    record = {
        "url": "https://example.com/report.pdf",
        "status": "downloaded",
        "path": "data/raw/report.pdf",
    }

    asyncio.run(manifest.add(record))

    assert manifest.done(record["url"], tmp_path)

    downloaded_file.unlink()

    assert not manifest.done(record["url"], tmp_path)


def test_manifest_add_appends_jsonl(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    manifest = Manifest(manifest_path)

    record = {
        "url": "https://example.com/report.pdf",
        "status": "failed",
        "reason": "HTTP 404",
    }

    asyncio.run(manifest.add(record))

    lines = manifest_path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 1
    assert json.loads(lines[0]) == record
    assert manifest.records[record["url"]] == record


# --------------------------------------------------
# 5. Robots.txt tests
# --------------------------------------------------


def test_robots_blocks_disallowed_url():
    async def run_test():
        def handler(request):
            assert request.url.path == "/robots.txt"

            return httpx.Response(
                200,
                text=("User-agent: examate-student-bot\nDisallow: /private\n"),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            robots = Robots(client)

            allowed, delay = await robots.allowed(
                "https://example.com/private/report.pdf"
            )

            assert allowed is False
            assert delay == 0.0

    asyncio.run(run_test())


def test_robots_fails_closed_on_server_error():
    async def run_test():
        def handler(_request):
            return httpx.Response(503)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            robots = Robots(client)

            allowed, _delay = await robots.allowed("https://example.com/report.pdf")

            assert allowed is False

    asyncio.run(run_test())


# --------------------------------------------------
# 6. Host rate-limiting test
# --------------------------------------------------


def test_host_gate_wait_and_release():
    async def run_test():
        gate = HostGate()
        url = "https://example.com/report.pdf"

        lock = await gate.wait(url, 0)

        assert lock.locked()

        gate.release(url)

        assert not lock.locked()
        assert "example.com" in gate.last_request

    asyncio.run(run_test())


# --------------------------------------------------
# 7. Download tests
# --------------------------------------------------


def test_download_saves_file_and_checksum(tmp_path):
    async def run_test():
        body = b"Example cybersecurity document."

        def handler(_request):
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=body,
            )

        source = Source(
            url="https://example.com/report.pdf",
            source="example",
            licence="Test licence",
            title="Example Report",
        )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            record = await _download(
                client,
                source,
                tmp_path,
            )

        downloaded_file = tmp_path / record["path"]

        assert record["status"] == "downloaded"
        assert downloaded_file.is_file()
        assert downloaded_file.read_bytes() == body
        assert record["bytes"] == len(body)
        assert record["sha256"] == hashlib.sha256(body).hexdigest()
        assert record["http_status"] == 200
        assert record["title"] == "Example Report"

    asyncio.run(run_test())


def test_download_rejects_oversized_document(tmp_path):
    async def run_test():
        def handler(_request):
            return httpx.Response(
                200,
                headers={"content-type": "application/pdf"},
                content=b"123456789",
            )

        source = Source(
            url="https://example.com/large.pdf",
            source="example",
            licence="Test licence",
        )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(DownloadError, match="exceeds"):
                await _download(
                    client,
                    source,
                    tmp_path,
                    max_bytes=4,
                )

        raw_directory = tmp_path / "data" / "raw"

        assert not list(raw_directory.rglob("*.part"))
        assert not list(raw_directory.rglob("*.pdf"))

    asyncio.run(run_test())


# --------------------------------------------------
# 8. Resumption test
# --------------------------------------------------


def test_fetch_all_skips_already_downloaded_file(tmp_path):
    async def run_test():
        url = "https://example.com/report.pdf"

        source = Source(
            url=url,
            source="example",
            licence="Test licence",
            title="Example Report",
        )

        # Simulate a document downloaded during an earlier run.
        relative_path = f"data/raw/example/{file_stem(url)}.pdf"

        downloaded_file = tmp_path / relative_path
        downloaded_file.parent.mkdir(parents=True)
        downloaded_file.write_bytes(b"Previously downloaded document")

        # Record the successful download in the manifest.
        manifest = Manifest(tmp_path / "data" / "manifest.jsonl")

        await manifest.add(
            {
                "url": url,
                "source": "example",
                "title": "Example Report",
                "licence": "Test licence",
                "status": "downloaded",
                "path": relative_path,
            }
        )

        # Any HTTP request would mean the downloader failed to skip it.
        def handler(request):
            raise AssertionError(f"Unexpected HTTP request: {request.url}")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            counts = await fetch_all(
                sources=[source],
                root=tmp_path,
                client=client,
            )

        assert counts["skipped"] == 1
        assert counts["downloaded"] == 0
        assert counts["failed"] == 0

        # Confirm the original file remains unchanged.
        assert downloaded_file.read_bytes() == (b"Previously downloaded document")

    asyncio.run(run_test())


def test_download_resumes_partial_file(tmp_path):
    async def run_test():
        import hashlib

        from src.controlmap.ingest.fetch import file_stem, slug

        document = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        partial = document[:10]
        remaining = document[len(partial) :]

        source = Source(
            url="https://example.com/test-document.pdf",
            source="resume-test",
            licence="Test licence",
            title="Resume Test Document",
        )

        output_directory = tmp_path / "data" / "raw" / slug(source.source)
        output_directory.mkdir(parents=True, exist_ok=True)

        temporary = output_directory / f"{file_stem(source.url)}.download.part"
        temporary.write_bytes(partial)

        requests = []

        def handler(request):
            requests.append(request)

            if request.headers.get("Range") == f"bytes={len(partial)}-":
                return httpx.Response(
                    206,
                    headers={
                        "Content-Type": "application/pdf",
                        "Content-Range": (
                            f"bytes {len(partial)}-{len(document) - 1}/{len(document)}"
                        ),
                    },
                    content=remaining,
                )

            return httpx.Response(
                200,
                headers={"Content-Type": "application/pdf"},
                content=document,
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            record = await _download(client, source, tmp_path)

        destination = tmp_path / record["path"]

        assert record["status"] == "downloaded"
        assert record["bytes"] == len(document)
        assert destination.read_bytes() == document
        assert record["sha256"] == hashlib.sha256(document).hexdigest()
        assert not temporary.exists()

        assert len(requests) == 1
        assert requests[0].headers["Range"] == f"bytes={len(partial)}-"

    asyncio.run(run_test())
