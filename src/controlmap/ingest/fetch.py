"""Polite, asynchronous, resumable document downloader for ControlMap."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import json
import random
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from protego import Protego

USER_AGENT = (
    "examate-student-bot/0.1 "
    "(student project; "
    "+https://github.com/harinishankarmn092827/prince28-sec10-controlmap)"
)

ROBOTS_TOKEN = "examate-student-bot"

RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
MAX_WAIT = 120
MAX_BYTES = 200 * 1024 * 1024

EXT_BY_TYPE = {
    "application/pdf": ".pdf",
    "application/json": ".json",
    "text/html": ".html",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "application/xml": ".xml",
    "text/xml": ".xml",
}


@dataclass(frozen=True)
class Source:
    """Metadata describing a document to download."""

    url: str
    source: str
    licence: str
    title: str = ""


class DownloadError(Exception):
    """Raised when a document cannot be downloaded."""


def now_iso() -> str:
    """Return the current UTC time in ISO format."""
    return datetime.now(UTC).isoformat()


def slug(value: str) -> str:
    """Convert a string into a filesystem-friendly name."""
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value)
    return value.strip("-._") or "document"


def file_stem(url: str) -> str:
    """Create a stable filename from a URL."""
    parsed = urlparse(url)
    name = Path(parsed.path).stem or "document"
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
    return f"{slug(name)[:70]}-{digest}"


def pick_ext(url: str, content_type: str | None) -> str:
    """Determine a file extension from the URL or response type."""
    path = urlparse(url).path
    suffix = Path(path).suffix.lower()

    media_type = (content_type or "").split(";", 1)[0].strip().lower()

    # Some PDF download endpoints use .cfm in the URL.
    # Prefer the actual response type for these endpoints.
    if suffix == ".cfm" and media_type in EXT_BY_TYPE:
        return EXT_BY_TYPE[media_type]

    if suffix and len(suffix) <= 10:
        return suffix

    return EXT_BY_TYPE.get(media_type, ".bin")


def backoff_delay(attempt: int) -> float:
    """Return exponential backoff with random jitter."""
    base = min(2**attempt, MAX_WAIT)
    return min(base + random.uniform(0, 1), MAX_WAIT)


def retry_after_seconds(value: str | None) -> float | None:
    """Parse Retry-After as seconds or an HTTP date."""
    if not value:
        return None

    try:
        return min(max(float(value), 0), MAX_WAIT)
    except ValueError:
        pass

    try:
        retry_time = parsedate_to_datetime(value)

        if retry_time.tzinfo is None:
            retry_time = retry_time.replace(tzinfo=UTC)

        seconds = (retry_time - datetime.now(UTC)).total_seconds()
        return min(max(seconds, 0), MAX_WAIT)

    except (TypeError, ValueError, OverflowError):
        return None


def read_sources(path: Path) -> list[Source]:
    """Read and validate document sources from a CSV file."""
    sources = []

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        required = {"url", "source", "licence"}
        headers = set(reader.fieldnames or [])

        if not required.issubset(headers):
            raise ValueError(
                "sources.csv must contain the columns "
                "url, source, and licence. The title column is optional."
            )

        for line_number, row in enumerate(reader, start=2):
            url = (row.get("url") or "").strip()
            source = (row.get("source") or "").strip()
            licence = (row.get("licence") or "").strip()
            title = (row.get("title") or "").strip()

            parsed = urlparse(url)

            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError(
                    f"Invalid HTTP(S) URL on CSV line {line_number}: {url}"
                )

            if not source or not licence:
                raise ValueError(
                    f"Source and licence are required on CSV line {line_number}"
                )

            sources.append(
                Source(
                    url=url,
                    source=source,
                    licence=licence,
                    title=title,
                )
            )

    return sources


class Manifest:
    """Read and append download records to a JSON Lines manifest."""

    def __init__(self, path: Path):
        self.path = path
        self.records: dict[str, dict] = {}
        self.lock = asyncio.Lock()

        path.parent.mkdir(parents=True, exist_ok=True)

        if not path.exists():
            return

        with path.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    # Ignore an incomplete or malformed manifest line.
                    continue

                if isinstance(record, dict) and record.get("url"):
                    self.records[record["url"]] = record

    def done(self, url: str, root: Path) -> bool:
        """Check whether a completed download still exists."""
        record = self.records.get(url)

        if not record or record.get("status") != "downloaded":
            return False

        relative_path = record.get("path")

        if not relative_path:
            return False

        path = root / relative_path
        return path.is_file()

    async def add(self, record: dict) -> None:
        """Append a record safely, including when tasks run concurrently."""
        async with self.lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

            self.records[record["url"]] = record


class Robots:
    """Cache robots.txt rules and check whether a URL may be fetched."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.cache: dict[str, tuple[Protego | None, bool, float]] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    async def allowed(self, url: str) -> tuple[bool, float]:
        """Return whether the URL is allowed and its crawl delay."""
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        if origin not in self.locks:
            self.locks[origin] = asyncio.Lock()

        async with self.locks[origin]:
            if origin not in self.cache:
                robots_url = f"{origin}/robots.txt"

                try:
                    response = await self.client.get(
                        robots_url,
                        timeout=30,
                    )

                    if response.status_code == 429 or response.status_code >= 500:
                        # Fail closed when robots.txt cannot be checked
                        # because of a temporary server problem.
                        self.cache[origin] = (None, False, 0.0)

                    elif response.status_code >= 400:
                        # An ordinary 4xx response means no rules
                        # are available from this robots.txt request.
                        self.cache[origin] = (
                            Protego.parse(""),
                            True,
                            0.0,
                        )

                    else:
                        rules = Protego.parse(response.text)
                        delay = rules.crawl_delay(ROBOTS_TOKEN) or 0.0

                        self.cache[origin] = (
                            rules,
                            True,
                            float(delay),
                        )

                except (httpx.HTTPError, ValueError):
                    # Do not silently permit access if the check fails.
                    self.cache[origin] = (None, False, 0.0)

            rules, reachable, delay = self.cache[origin]

            if not reachable or rules is None:
                return False, delay

            return bool(rules.can_fetch(url, ROBOTS_TOKEN)), delay


class HostGate:
    """Serialize requests to each host and enforce a minimum delay."""

    def __init__(self):
        self.locks: dict[str, asyncio.Lock] = {}
        self.last_request: dict[str, float] = {}

    async def wait(self, url: str, delay: float) -> asyncio.Lock:
        """Acquire the host lock and wait until the delay has elapsed."""
        host = urlparse(url).netloc.lower()

        if host not in self.locks:
            self.locks[host] = asyncio.Lock()

        lock = self.locks[host]
        await lock.acquire()

        elapsed = asyncio.get_running_loop().time() - self.last_request.get(host, 0.0)

        if elapsed < delay:
            await asyncio.sleep(delay - elapsed)

        return lock

    def release(self, url: str) -> None:
        """Record the request time and release the host lock."""
        host = urlparse(url).netloc.lower()
        self.last_request[host] = asyncio.get_running_loop().time()
        self.locks[host].release()


def make_client(max_concurrency: int = 4) -> httpx.AsyncClient:
    """Create an HTTP client with timeouts and connection limits."""
    return httpx.AsyncClient(
        headers={"User-Agent": USER_AGENT},
        timeout=httpx.Timeout(30, connect=10),
        limits=httpx.Limits(
            max_connections=max_concurrency,
            max_keepalive_connections=max_concurrency,
        ),
        follow_redirects=True,
    )


async def _download(
    client: httpx.AsyncClient,
    source: Source,
    root: Path,
    max_bytes: int = MAX_BYTES,
) -> dict:
    """Stream a single response to a temporary file, then rename it."""
    relative_directory = Path("data") / "raw" / slug(source.source)
    output_directory = root / relative_directory
    output_directory.mkdir(parents=True, exist_ok=True)

    filename = file_stem(source.url)
    digest = hashlib.sha256()
    size = 0

    destination: Path | None = None
    temporary: Path | None = None

    try:
        # One GET request per attempt; stream its response to disk.
        async with client.stream(
            "GET",
            source.url,
            timeout=30,
        ) as response:
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            extension = pick_ext(source.url, content_type)

            destination = output_directory / f"{filename}{extension}"
            temporary = destination.with_suffix(destination.suffix + ".part")

            with temporary.open("wb") as file:
                async for chunk in response.aiter_bytes():
                    size += len(chunk)

                    if size > max_bytes:
                        raise DownloadError(
                            f"Document exceeds the {max_bytes}-byte limit"
                        )

                    digest.update(chunk)
                    file.write(chunk)

            http_status = response.status_code

        # Expose the final file only after the complete response is written.
        temporary.replace(destination)

    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise

    return {
        "url": source.url,
        "source": source.source,
        "title": source.title,
        "licence": source.licence,
        "status": "downloaded",
        "path": destination.relative_to(root).as_posix(),
        "bytes": size,
        "sha256": digest.hexdigest(),
        "content_type": content_type,
        "http_status": http_status,
        "downloaded_at": now_iso(),
    }


async def fetch_one(
    source: Source,
    root: Path,
    client: httpx.AsyncClient,
    robots: Robots,
    gate: HostGate,
    semaphore: asyncio.Semaphore,
    manifest: Manifest,
    per_host_delay: float = 0.5,
    max_attempts: int = 4,
    sleep: Callable = asyncio.sleep,
) -> dict:
    """Download one source with robots checks, limits, and retries."""
    record_base = {
        "url": source.url,
        "source": source.source,
        "title": source.title,
        "licence": source.licence,
    }

    allowed, robots_delay = await robots.allowed(source.url)

    if not allowed:
        return {
            **record_base,
            "status": "blocked",
            "reason": "Robots rules prohibit access or could not be checked",
            "checked_at": now_iso(),
        }

    delay = max(per_host_delay, robots_delay)

    for attempt in range(max_attempts):
        try:
            async with semaphore:
                await gate.wait(source.url, delay)

                try:
                    result = await _download(client, source, root)
                finally:
                    gate.release(source.url)

            await manifest.add(result)
            return result

        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code

            if status not in RETRYABLE or attempt == max_attempts - 1:
                return {
                    **record_base,
                    "status": "failed",
                    "reason": f"HTTP {status}",
                    "checked_at": now_iso(),
                }

            wait = retry_after_seconds(exc.response.headers.get("Retry-After"))

            await sleep(wait if wait is not None else backoff_delay(attempt))

        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt == max_attempts - 1:
                return {
                    **record_base,
                    "status": "failed",
                    "reason": "Network error after retries",
                    "checked_at": now_iso(),
                }

            await sleep(backoff_delay(attempt))

        except (DownloadError, OSError) as exc:
            return {
                **record_base,
                "status": "failed",
                "reason": str(exc),
                "checked_at": now_iso(),
            }

    return {
        **record_base,
        "status": "failed",
        "reason": "Retry limit reached",
        "checked_at": now_iso(),
    }


async def fetch_all(
    sources: list[Source],
    root: Path = Path("."),
    max_concurrency: int = 4,
    per_host_delay: float = 0.5,
    max_attempts: int = 4,
    client: httpx.AsyncClient | None = None,
    sleep: Callable = asyncio.sleep,
    on_result: Callable | None = None,
) -> dict[str, int]:
    """Download sources, skip completed files, and return summary counts."""
    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")

    if per_host_delay < 0:
        raise ValueError("per_host_delay cannot be negative")

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    root = Path(root)
    raw_directory = root / "data" / "raw"
    raw_directory.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(root / "data" / "manifest.jsonl")
    semaphore = asyncio.Semaphore(max_concurrency)
    gate = HostGate()

    counts = {
        "downloaded": 0,
        "skipped": 0,
        "blocked": 0,
        "failed": 0,
    }

    own_client = client is None

    if client is None:
        client = make_client(max_concurrency)

    robots = Robots(client)

    async def process(source: Source) -> None:
        if manifest.done(source.url, root):
            counts["skipped"] += 1

            if on_result:
                on_result(
                    {
                        "url": source.url,
                        "status": "skipped",
                    }
                )

            return

        record = await fetch_one(
            source=source,
            root=root,
            client=client,
            robots=robots,
            gate=gate,
            semaphore=semaphore,
            manifest=manifest,
            per_host_delay=per_host_delay,
            max_attempts=max_attempts,
            sleep=sleep,
        )

        # Successful records are written by fetch_one.
        # Record blocked and failed attempts as well.
        if record["status"] != "downloaded":
            await manifest.add(record)

        counts[record["status"]] += 1

        if on_result:
            on_result(record)

    try:
        await asyncio.gather(*(process(source) for source in sources))
    finally:
        if own_client:
            await client.aclose()

    return counts
