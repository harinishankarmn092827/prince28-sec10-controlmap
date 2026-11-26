"""Classify questions using versioned prompts and the existing LLM gateway."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from controlmap.llm.gateway import LLMGateway
from controlmap.llm.prompts import load_prompt

ClassificationLabel = Literal["docs", "personal", "off_topic"]


@dataclass(frozen=True)
class ClassificationResult:
    """Validated result from the question classifier."""

    label: ClassificationLabel
    reason: str
    prompt_version: int


def parse_classification(
    content: str,
    prompt_version: int,
) -> ClassificationResult:
    """Parse and validate a model's JSON classification."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError("Classifier returned invalid JSON") from exc

    if not isinstance(data, dict):
        raise ValueError("Classifier response must be a JSON object")

    label = data.get("label")
    reason = data.get("reason", "")

    if label not in {"docs", "personal", "off_topic"}:
        raise ValueError(f"Invalid classification label: {label!r}")

    if not isinstance(reason, str):
        raise ValueError("Classification reason must be a string")

    return ClassificationResult(
        label=label,
        reason=reason,
        prompt_version=prompt_version,
    )


async def classify_question(
    question: str,
    version: int = 3,
    prompts_dir: str | Path | None = None,
) -> ClassificationResult:
    """Classify one question using a selected prompt version."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question must not be empty")

    system_prompt = load_prompt("classify", version, prompts_dir)
    gateway = LLMGateway(system_prompt=system_prompt)

    response = await gateway.generate(
        [{"role": "user", "content": question.strip()}],
        response_format={"type": "json_object"},
    )

    return parse_classification(response.content, version)
