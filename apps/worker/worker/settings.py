from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Runtime role (non-owner, RLS enforced) — same convention as the API.
    app_database_url: str = "postgresql://ops_app:ops_app@localhost:5432/ops_engine"
    redis_url: str = "redis://localhost:6379/0"

    litellm_base_url: str = "http://localhost:4000"
    # Fernet key for tenants.litellm_key_encrypted — must match the API's.
    # Empty = keys are read as-is (tests / gateway disabled).
    litellm_key_encryption_key: str = ""

    storage_endpoint: str = ""
    storage_bucket: str = "vault"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = "auto"

    sentry_dsn: str = ""
    environment: str = "dev"

    # Resend email transport for the weekly claims digest. Empty key = the
    # digest cron runs its sweep but sends nothing. All three must match the
    # API's values — the API verifies the unsubscribe links this side signs.
    resend_api_key: str = ""
    email_from: str = "Flowgrid <notifications@flowgridos.co.uk>"
    email_unsubscribe_secret: str = ""
    # Two origins on purpose: register links land on the web app, the
    # unsubscribe link lands on the API (which serves /email/digest itself).
    web_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    chunk_target_tokens: int = 600
    chunk_overlap_ratio: float = 0.15
    embed_batch_size: int = 64


@lru_cache
def get_settings() -> Settings:
    return Settings()
