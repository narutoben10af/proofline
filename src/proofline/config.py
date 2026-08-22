from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Proofline"
    api_schema_version: str = "1.0.0"
    model_provider: str = "gemma"
    gemma_model: str = "gemma-4-26b-a4b-it"
    google_api_key: str | None = Field(
        default=None, validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY")
    )
    gemini_request_timeout_seconds: float = Field(default=30.0, ge=1, le=60)
    gemini_max_retries: int = Field(default=1, ge=0, le=2)


@lru_cache
def get_settings() -> Settings:
    return Settings()
