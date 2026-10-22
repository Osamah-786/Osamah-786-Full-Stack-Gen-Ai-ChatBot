"""Validated application settings loaded from the environment or backend .env."""

from typing import Annotated
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by backend modules."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    supabase_url: str
    supabase_anon_key: SecretStr
    supabase_service_role_key: SecretStr
    database_url: SecretStr

    groq_api_key: SecretStr
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_chat_model: str = "openai/gpt-oss-120b"
    groq_grounding_model: str = "openai/gpt-oss-20b"
    retrieval_fts_keyword_model: str = "openai/gpt-oss-20b"

    allowed_origins: Annotated[list[str], NoDecode]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
