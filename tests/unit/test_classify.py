"""Unit tests for versioned question classification."""

import asyncio

import pytest

from controlmap.llm import classify as classify_module
from controlmap.llm.classify import classify_question, parse_classification
from controlmap.llm.prompts import list_prompt_versions


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('{"label":"docs","reason":"Framework question"}', "docs"),
        ('{"label":"personal","reason":"Private information"}', "personal"),
        ('{"label":"off_topic","reason":"Unrelated request"}', "off_topic"),
    ],
)
def test_parse_classification_accepts_valid_labels(content, expected):
    result = parse_classification(content, 2)

    assert result.label == expected
    assert result.prompt_version == 2


def test_parse_classification_rejects_invalid_json():
    with pytest.raises(ValueError, match="invalid JSON"):
        parse_classification("not json", 1)


def test_parse_classification_rejects_unknown_label():
    with pytest.raises(ValueError, match="Invalid classification label"):
        parse_classification(
            '{"label":"maybe","reason":"Uncertain"}',
            1,
        )


def test_parse_classification_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_classification('["docs"]', 1)


def test_prompt_versions_are_sorted():
    assert list_prompt_versions("classify") == [1, 2, 3, 4]


def test_classify_question_uses_gateway_and_selected_version(monkeypatch):
    calls = {}

    class FakeResponse:
        content = '{"label":"docs","reason":"Security compliance question"}'

    class FakeGateway:
        def __init__(self, system_prompt):
            calls["system_prompt"] = system_prompt

        async def generate(self, messages, response_format=None):
            calls["messages"] = messages
            return FakeResponse()

    monkeypatch.setattr(classify_module, "LLMGateway", FakeGateway)

    result = asyncio.run(classify_question("What is NIST CSF?", version=2))

    assert result.label == "docs"
    assert result.prompt_version == 2
    assert "NIST CSF" in calls["messages"][0]["content"]
    assert "ControlMap" in calls["system_prompt"]


def test_classify_question_rejects_empty_question():
    with pytest.raises(ValueError, match="must not be empty"):
        asyncio.run(classify_question("   ", version=1))
