from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://ops:ops@localhost:5432/ops_engine"
    # Role the API connects as. Must NOT own the tables (RLS is FORCEd, but
    # a non-owner app role is defence in depth). Migrations use database_url.
    app_database_url: str = ""

    # Supabase auth: either a JWKS URL (asymmetric keys) or the legacy shared
    # secret (HS256). If both are set, JWKS wins.
    supabase_jwks_url: str = ""
    supabase_jwt_secret: str = ""
    jwt_audience: str = "authenticated"

    redis_url: str = ""
    sentry_dsn: str = ""
    environment: str = "dev"

    # LiteLLM proxy. Empty base URL = gateway disabled (unit tests, CI):
    # tenant bootstrap then leaves litellm_key_id null and chat returns 503.
    litellm_base_url: str = ""
    litellm_master_key: str = ""

    chat_rate_limit_per_min: int = 60
    upload_rate_limit_per_hour: int = 20

    # Object storage (MinIO in dev, Cloudflare R2 in prod). Empty endpoint =
    # storage disabled (unit tests, CI): vault endpoints return 503.
    storage_endpoint: str = ""
    storage_bucket: str = "vault"
    storage_access_key: str = ""
    storage_secret_key: str = ""
    storage_region: str = "auto"

    trial_days: int = 14
    default_seats: int = 3
    default_soft_budget_per_seat_usd: float = 1.50

    @property
    def effective_app_database_url(self) -> str:
        return self.app_database_url or self.database_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
