"""Application configuration via Pydantic Settings (12-factor: всё из env)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- environment ---
    environment: Literal["dev", "prod", "test"] = "dev"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # --- service identity ---
    service_name: str = "meshnest-api"
    public_url: str = "http://localhost:8000"  # внешний origin (для CORS / email links)
    frontend_url: str = "http://localhost:5173"

    # --- database ---
    database_url: str = "postgresql+asyncpg://meshnest:meshnest@postgres:5432/meshnest"
    database_url_sync: str = "postgresql+psycopg2://meshnest:meshnest@postgres:5432/meshnest"
    db_pool_size: int = 10
    db_max_overflow: int = 5

    # --- redis ---
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # --- object storage (MinIO / S3) ---
    s3_endpoint_url: str = "http://minio:9000"
    s3_region: str = "us-east-1"
    s3_access_key: SecretStr = SecretStr("minioadmin")
    s3_secret_key: SecretStr = SecretStr("minioadmin")
    s3_bucket_files: str = "meshnest-files"
    s3_bucket_derived: str = "meshnest-derived"
    s3_bucket_imports: str = "meshnest-imports"
    s3_use_ssl: bool = False
    s3_presigned_ttl: int = 300  # seconds

    # --- search ---
    meilisearch_url: str = "http://meilisearch:7700"
    meilisearch_master_key: SecretStr = SecretStr("change-me-master-key")
    meilisearch_index_models: str = "models"

    # --- auth ---
    jwt_secret: SecretStr = SecretStr("change-me-jwt-secret-min-32-bytes-required-here")
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_min: int = 15
    jwt_refresh_ttl_days: int = 7
    bcrypt_rounds: int = 12
    invite_default_ttl_days: int = 7

    # --- upload limits ---
    upload_chunk_max_bytes: int = 90 * 1024 * 1024  # 90 MB (под Cloudflare Free 100 MB)
    upload_max_total_bytes: int = 100 * 1024 * 1024 * 1024  # 100 GB

    # --- SMTP ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "MeshNest <noreply@meshnest.local>"
    smtp_use_tls: bool = True

    # --- rate limiting ---
    rate_limit_login: str = "5/minute"
    rate_limit_invite_redeem: str = "3/minute"
    rate_limit_uploads: str = "30/minute"
    rate_limit_default: str = "60/minute"

    # --- CORS ---
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    @computed_field
    @property
    def is_production(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    """Cached settings — для DI в FastAPI и Celery."""
    return Settings()


settings = get_settings()
