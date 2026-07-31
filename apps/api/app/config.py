from functools import lru_cache

from pydantic import field_validator
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
    # tenant bootstrap then leaves the tenant key null and chat returns 503.
    litellm_base_url: str = ""
    litellm_master_key: str = ""
    # Fernet key encrypting tenants.litellm_key_encrypted at rest. Required
    # whenever the gateway is enabled (enforced at app startup). Generate:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    litellm_key_encryption_key: str = ""

    chat_rate_limit_per_min: int = 60
    upload_rate_limit_per_hour: int = 20

    # Comma-separated browser origins; prod sets the tenant-facing domain(s).
    # Wildcards are rejected — origins must be enumerated explicitly.
    cors_origins: str = "http://localhost:3000"

    @field_validator("cors_origins")
    @classmethod
    def _no_wildcard_origins(cls, v: str) -> str:
        origins = [o.strip() for o in v.split(",") if o.strip()]
        if not origins:
            raise ValueError("cors_origins must list at least one origin")
        for origin in origins:
            if "*" in origin:
                raise ValueError(
                    "wildcard CORS origins are not allowed; enumerate origins explicitly"
                )
        return ",".join(origins)

    @property
    def cors_origin_list(self) -> list[str]:
        return self.cors_origins.split(",")

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
