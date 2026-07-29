from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime role (non-owner, RLS enforced) — same convention as the API.
    app_database_url: str = "postgresql://ops_app:ops_app@localhost:5432/ops_engine"
    redis_url: str = "redis://localhost:6379/0"

    litellm_base_url: str = "http://localhost:4000"

    storage_endpoint: str = ""
    storage_bucket: str = "vault"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = "auto"

    sentry_dsn: str = ""
    environment: str = "dev"

    chunk_target_tokens: int = 600
    chunk_overlap_ratio: float = 0.15
    embed_batch_size: int = 64


@lru_cache
def get_settings() -> Settings:
    return Settings()
