"""Application configuration for ControlMap."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application, LLM gateway, and ingestion queue settings."""

    app_name: str = "ControlMap"
    api_version: str = "v1"
    debug: bool = False

    data_file: Path = Path("app/data/sample_records.json")
    database_url: str

    # LLM provider credentials
    gemini_api_key: str = ""
    groq_api_key: str = ""

    # LLM provider models
    llm_primary_model: str = "gemini-3.8-flash"
    llm_fallback_model: str = "openai/gpt-oss-20b"

    # OpenAI-compatible provider endpoints
    llm_primary_base_url: str = (
        "https://generativelanguage.googleapis.com/v1beta/openai"
    )
    llm_fallback_base_url: str = "https://api.groq.com/openai/v1"

    # Gateway configuration
    llm_timeout_seconds: float = 30.0
    usd_inr: float = 95.0
    prompts_dir: Path = Path("prompts")

    # Async ingestion queue
    redis_url: str = "redis://localhost:6379"
    manifest_file: Path = Path("data/manifest.jsonl")
    admin_token: str = ""
    worker_in_api: bool = False
    ingest_concurrency: int = 2
    ingest_rpm: float = 12.0
    ingest_job_timeout: int = 60
    ingest_max_tries: int = 3

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
