"""Check Gemini and Groq connectivity with direct HTTP requests."""

import asyncio
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

TIMEOUT_SECONDS = 30.0

PROVIDERS = [
    {
        "name": "gemini",
        "key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model_env": "LLM_PRIMARY_MODEL",
        "default_model": "gemini-3.8-flash",
    },
    {
        "name": "groq",
        "key_env": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "model_env": "LLM_FALLBACK_MODEL",
        "default_model": "openai/gpt-oss-20b",
    },
]


async def ping_provider(
    client: httpx.AsyncClient,
    provider: dict,
) -> bool:
    """Send one direct HTTP request to a provider."""
    name = provider["name"]
    api_key = os.getenv(provider["key_env"], "").strip()
    model = os.getenv(
        provider["model_env"],
        provider["default_model"],
    ).strip()

    if not api_key:
        print(f"{name:<8} MISSING  {provider['key_env']} is not configured")
        return False

    url = f"{provider['base_url']}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
        "max_tokens": 10,
    }

    started = time.perf_counter()

    try:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if response.is_error:
            try:
                error_data = response.json()

                if isinstance(error_data, dict):
                    detail = error_data.get("error", error_data)
                    if isinstance(detail, dict):
                        message = detail.get(
                            "message",
                            str(detail.get("code", "Unknown provider error")),
                        )
                    else:
                        message = str(detail)
                else:
                    message = str(error_data)
            except ValueError:
                message = "Provider returned a non-JSON error"

            print(f"{name:<8} FAIL     HTTP {response.status_code} in {elapsed_ms} ms")
            print(f"         Reason: {message[:500]}")
            return False

        data = response.json()
        choices = data.get("choices", []) if isinstance(data, dict) else []
        answer = ""

        if choices and isinstance(choices[0], dict):
            answer = choices[0].get("message", {}).get("content", "")

        answer = " ".join(str(answer).split())
        usage = data.get("usage") or {}

        print(
            f"{name:<8} OK       {model} said {answer!r} "
            f"in {elapsed_ms} ms, "
            f"tokens in={usage.get('prompt_tokens', '?')} "
            f"out={usage.get('completion_tokens', '?')}"
        )
        return True

    except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        print(f"{name:<8} FAIL     {type(exc).__name__} in {elapsed_ms} ms")
        return False


async def main() -> int:
    """Ping both providers independently."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        results = [await ping_provider(client, provider) for provider in PROVIDERS]

    passed = sum(results)
    print(f"\nProvider checks passed: {passed}/{len(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
