from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
