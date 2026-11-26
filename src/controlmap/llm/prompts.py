"""Load and enumerate versioned prompts."""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import settings

_VERSION_PATTERN = re.compile(r"^(?P<task>.+)_v(?P<version>\d+)\.md$")


def _prompts_directory(prompts_dir: str | Path | None = None) -> Path:
    """Return the configured or explicitly supplied prompts directory."""
    return Path(prompts_dir) if prompts_dir is not None else settings.prompts_dir


def list_prompt_versions(
    task: str,
    prompts_dir: str | Path | None = None,
) -> list[int]:
    """Return available numeric versions for a prompt task, in ascending order."""
    directory = _prompts_directory(prompts_dir)

    if not directory.is_dir():
        return []

    versions = []

    for path in directory.glob(f"{task}_v*.md"):
        match = _VERSION_PATTERN.match(path.name)

        if match and match.group("task") == task:
            versions.append(int(match.group("version")))

    return sorted(set(versions))


def load_prompt(
    task: str,
    version: int,
    prompts_dir: str | Path | None = None,
) -> str:
    """Load a specific version of a prompt or raise a helpful error."""
    if version < 1:
        raise ValueError("Prompt version must be at least 1")

    path = _prompts_directory(prompts_dir) / f"{task}_v{version}.md"

    try:
        content = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Prompt not found: task={task!r}, version={version}, path={path}"
        ) from exc

    if not content:
        raise ValueError(f"Prompt is empty: {path}")

    return content
