"""Command-line interface for the ControlMap document collection pipeline."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Allow execution using: python scripts/fetch.py
ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.controlmap.ingest.fetch import (  # noqa: E402
    USER_AGENT,
    Manifest,
    Source,
    fetch_all,
    now_iso,
    read_sources,
    slug,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Collect documents for the ControlMap project."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Door 1: Download URLs from data/sources.csv.
    urls = subparsers.add_parser(
        "urls",
        help="Download URLs listed in data/sources.csv.",
    )
    urls.add_argument("--delay", type=float, default=0.5)
    urls.add_argument("--max-concurrency", type=int, default=4)
    urls.add_argument("--max-attempts", type=int, default=4)

    # Door 2: Clone a repository and register matching files.
    repo = subparsers.add_parser(
        "repo",
        help="Collect matching files from a Git repository.",
    )
    repo.add_argument("repository", help="GitHub owner/repository or Git URL.")
    repo.add_argument("--path", default=".")
    repo.add_argument("--ext", default=".json")
    repo.add_argument("--source", required=True)
    repo.add_argument("--licence", required=True)

    # Door 3: Discover URLs from a sitemap and append them to sources.csv.
    sitemap = subparsers.add_parser(
        "sitemap",
        help="Discover document URLs from a sitemap.",
    )
    sitemap.add_argument("url")
    sitemap.add_argument("--include", default="/")
    sitemap.add_argument("--limit", type=int, default=300)
    sitemap.add_argument("--source", required=True)
    sitemap.add_argument("--licence", required=True)

    # Door 4: Register files that were downloaded manually.
    manual = subparsers.add_parser(
        "manual",
        help="Register a manually downloaded file or directory.",
    )
    manual.add_argument("path", type=Path)
    manual.add_argument("--from-url", required=True)
    manual.add_argument("--source", required=True)
    manual.add_argument("--licence", required=True)

    return parser.parse_args()


def append_sources(sources: list[Source]) -> int:
    """Append new URLs to data/sources.csv without duplicating URLs."""
    csv_path = ROOT / "data" / "sources.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    existing: set[str] = set()

    if csv_path.exists():
        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            reader = csv.DictReader(file)
            existing = {(row.get("url") or "").strip() for row in reader}

    new_sources = [source for source in sources if source.url not in existing]

    if not new_sources:
        print("No new URLs to register.")
        return 0

    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with csv_path.open(
        "a",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["url", "source", "licence", "title"],
        )

        if write_header:
            writer.writeheader()

        for source in new_sources:
            writer.writerow(
                {
                    "url": source.url,
                    "source": source.source,
                    "licence": source.licence,
                    "title": source.title,
                }
            )

    print(f"Registered {len(new_sources)} new URL(s).")
    return len(new_sources)


async def run_urls(args: argparse.Namespace) -> int:
    """Run the asynchronous URL downloader."""
    csv_path = ROOT / "data" / "sources.csv"

    if not csv_path.exists():
        print(f"Sources file not found: {csv_path}")
        print("Create data/sources.csv with url, source, and licence columns.")
        return 1

    try:
        sources = read_sources(csv_path)
    except (OSError, ValueError) as exc:
        print(f"Could not read sources: {exc}")
        return 1

    if not sources:
        print("No sources found in data/sources.csv.")
        return 0

    print(f"Starting collection for {len(sources)} source(s).")

    def report(record: dict) -> None:
        status = record.get("status", "unknown")
        print(f"[{status.upper()}] {record.get('url', '')}")

    try:
        counts = await fetch_all(
            sources=sources,
            root=ROOT,
            max_concurrency=args.max_concurrency,
            per_host_delay=args.delay,
            max_attempts=args.max_attempts,
            on_result=report,
        )
    except (OSError, ValueError, httpx.HTTPError) as exc:
        print(f"Collection stopped: {exc}")
        return 1

    print("\nCollection summary")
    for status, count in counts.items():
        print(f"{status.capitalize()}: {count}")

    return 1 if counts["failed"] else 0


def run_repo(args: argparse.Namespace) -> int:
    """Clone a repository, copy matching files, and record their metadata."""
    repository = args.repository.strip()

    if repository.startswith("https://github.com/"):
        if not repository.endswith(".git"):
            repository += ".git"
    elif "/" in repository and "://" not in repository:
        repository = f"https://github.com/{repository}.git"

    if not repository.startswith(("https://", "http://", "git@")):
        print("Provide a valid Git repository URL or owner/repository.")
        return 1

    if args.ext and not args.ext.startswith("."):
        print("--ext must start with a dot, for example --ext .json")
        return 1

    requested_path = Path(args.path)

    if requested_path.is_absolute() or ".." in requested_path.parts:
        print("--path must be a relative repository path without '..'.")
        return 1

    output_dir = ROOT / "data" / "raw" / slug(args.source)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.TemporaryDirectory(prefix="controlmap-repo-") as temp:
            clone_dir = Path(temp) / "repository"

            print(f"Cloning {repository} ...")

            subprocess.run(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--filter=blob:none",
                    "--sparse",
                    repository,
                    str(clone_dir),
                ],
                check=True,
                timeout=300,
                capture_output=True,
                text=True,
            )

            subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone_dir),
                    "sparse-checkout",
                    "set",
                    args.path,
                ],
                check=True,
                timeout=60,
                capture_output=True,
                text=True,
            )

            commit = subprocess.run(
                [
                    "git",
                    "-C",
                    str(clone_dir),
                    "rev-parse",
                    "HEAD",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            source_dir = clone_dir / requested_path

            if not source_dir.exists():
                print(f"Repository path not found: {args.path}")
                return 1

            files = [
                path
                for path in source_dir.rglob("*")
                if path.is_file() and path.suffix.lower() == args.ext.lower()
            ]

            if not files:
                print(f"No {args.ext} files found under {args.path}.")
                return 0

            manifest = Manifest(ROOT / "data" / "manifest.jsonl")
            added = 0

            for file_path in files:
                relative = file_path.relative_to(source_dir)
                destination = output_dir / relative
                destination.parent.mkdir(parents=True, exist_ok=True)

                digest = hashlib.sha256()
                size = 0

                with file_path.open("rb") as source_file:
                    with destination.open("wb") as destination_file:
                        while chunk := source_file.read(1024 * 1024):
                            destination_file.write(chunk)
                            digest.update(chunk)
                            size += len(chunk)

                record = {
                    "url": (
                        f"{repository.removesuffix('.git')}/blob/"
                        f"{commit}/{requested_path.as_posix()}/"
                        f"{relative.as_posix()}"
                    ),
                    "source": args.source,
                    "title": file_path.name,
                    "licence": args.licence,
                    "status": "downloaded",
                    "path": destination.relative_to(ROOT).as_posix(),
                    "bytes": size,
                    "sha256": digest.hexdigest(),
                    "content_type": "application/json"
                    if file_path.suffix.lower() == ".json"
                    else "application/octet-stream",
                    "http_status": None,
                    "repository_commit": commit,
                    "downloaded_at": now_iso(),
                }

                # Repository entries use their file URL as the manifest key.
                if not manifest.done(record["url"], ROOT):
                    asyncio.run(manifest.add(record))
                    added += 1

            print(f"Repository commit: {commit}")
            print(f"Matching files found: {len(files)}")
            print(f"Files registered: {added}")

    except FileNotFoundError:
        print("Git was not found. Install Git and ensure it is on PATH.")
        return 1
    except subprocess.TimeoutExpired:
        print("Git operation timed out.")
        return 1
    except subprocess.CalledProcessError as exc:
        print("Git operation failed.")
        if exc.stderr:
            print(exc.stderr[-2000:])
        return 1
    except OSError as exc:
        print(f"File operation failed: {exc}")
        return 1

    return 0


def run_sitemap(args: argparse.Namespace) -> int:
    """Discover matching sitemap URLs and append them to the source CSV."""
    parsed = urlparse(args.url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        print("Provide a valid HTTP(S) sitemap URL.")
        return 1

    if args.limit < 1:
        print("--limit must be at least 1.")
        return 1

    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            response = client.get(args.url)
            response.raise_for_status()

        root = ET.fromstring(response.content)

    except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
        print(f"Could not read sitemap: {exc}")
        return 1

    discovered: list[Source] = []
    include = args.include

    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "loc":
            continue

        url = (element.text or "").strip()

        if not url:
            continue

        candidate = urlparse(url)

        if candidate.scheme not in {"http", "https"} or not candidate.hostname:
            continue

        if include and include not in candidate.path:
            continue

        discovered.append(
            Source(
                url=url,
                source=args.source,
                licence=args.licence,
                title=Path(candidate.path).name or candidate.netloc,
            )
        )

        if len(discovered) >= args.limit:
            break

    print(f"Matching sitemap URLs discovered: {len(discovered)}")
    append_sources(discovered)
    print("Sitemap discovery does not download documents.")

    return 0


def run_manual(args: argparse.Namespace) -> int:
    """Register manually downloaded files in the manifest."""
    file_path = args.path

    if not file_path.is_absolute():
        file_path = ROOT / file_path

    file_path = file_path.resolve()

    if not file_path.exists():
        print(f"Path not found: {file_path}")
        return 1

    parsed = urlparse(args.from_url)

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        print("--from-url must be a valid HTTP(S) URL.")
        return 1

    files = (
        [file_path]
        if file_path.is_file()
        else sorted(path for path in file_path.rglob("*") if path.is_file())
    )

    if not files:
        print("No files found to register.")
        return 0

    raw_dir = ROOT / "data" / "raw" / slug(args.source)
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(ROOT / "data" / "manifest.jsonl")
    registered = 0

    for item in files:
        if item.name.endswith(".part"):
            print(f"Skipping incomplete temporary file: {item}")
            continue

        if item.is_relative_to(raw_dir):
            destination = item
        else:
            destination = raw_dir / item.name
            shutil.copy2(item, destination)

        digest = hashlib.sha256()
        size = 0

        with destination.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)

        url = args.from_url

        if len(files) > 1:
            url = f"{args.from_url.rstrip('/')}#{item.name}"

        record = {
            "url": url,
            "source": args.source,
            "title": item.name,
            "licence": args.licence,
            "status": "downloaded",
            "path": destination.relative_to(ROOT).as_posix(),
            "bytes": size,
            "sha256": digest.hexdigest(),
            "content_type": None,
            "http_status": None,
            "registration_method": "manual",
            "registered_at": datetime.now(UTC).isoformat(),
        }

        if not manifest.done(url, ROOT):
            asyncio.run(manifest.add(record))
            registered += 1

    print(f"Files discovered: {len(files)}")
    print(f"Files registered: {registered}")

    return 0


def main() -> int:
    """Run the requested command."""
    args = parse_args()

    if args.command == "urls":
        return asyncio.run(run_urls(args))

    if args.command == "repo":
        return run_repo(args)

    if args.command == "sitemap":
        return run_sitemap(args)

    if args.command == "manual":
        return run_manual(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
