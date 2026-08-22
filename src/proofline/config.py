import tempfile
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Proofline"
    api_schema_version: str = "1.0.0"
    model_provider: str = "gemma"
    gemma_model: str = "gemma-4-26b-a4b-it"
    gemini_api_key: str | None = None
    gemini_request_timeout_seconds: float = 30.0
    gemini_max_retries: int = 1
    source_library_root: Path = Path(tempfile.gettempdir()) / "proofline-source-library"
    source_library_idle_minutes: int = 30
    source_library_absolute_minutes: int = 120
    source_library_cleanup_seconds: int = 60
    source_library_max_request_bytes: int = 21 * 1024 * 1024
    source_library_allowed_origins: str = (
        "https://testserver,http://127.0.0.1:8000,http://localhost:8000,"
        "http://127.0.0.1:4173,http://localhost:4173"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
