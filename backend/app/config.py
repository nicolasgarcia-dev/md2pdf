from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    max_markdown_bytes: int = 1 * 1024 * 1024
    max_upload_bytes: int = 2 * 1024 * 1024
    owner_max_markdown_bytes: int = 20 * 1024 * 1024
    owner_max_upload_bytes: int = 50 * 1024 * 1024

    rate_limit_per_minute: int = 20
    rate_limit_per_hour: int = 200

    bypass_token: str = ""
    trust_proxy_headers: bool = True

    cors_allow_origins: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


settings = Settings()
