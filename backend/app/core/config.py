from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Deep Bleue IA DocMind"
    app_env: Literal["dev", "test", "staging", "prod"] = "dev"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    database_url: str = "postgresql+asyncpg://docmind:docmind@localhost:5432/docmind"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_collection: str = "docmind_chunks"

    redis_url: str = "redis://localhost:6379/0"

    embedding_provider: Literal["mock", "openai"] = "mock"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    llm_provider: Literal["mock", "openai"] = "mock"
    llm_model: str = "gpt-4o"
    openai_api_key: str | None = None

    dev_auth_enabled: bool = True
    default_tenant_id: str = "deep-bleue-ia"
    allowed_email_domains: str = ""

    jwt_secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    local_connector_root: str = "./sample_docs"

    rag_top_k: int = 8
    rag_max_context_chars: int = 12000

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("openai_api_key", mode="before")
    @classmethod
    def strip_api_key(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
