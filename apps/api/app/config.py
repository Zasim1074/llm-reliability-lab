from typing import Literal, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str = "sqlite:///./llm_reliability.db"
    database_ssl_mode: Optional[Literal["disable", "allow", "prefer", "require", "verify-ca", "verify-full"]] = None
    cors_origins: str = "http://localhost:3000"
    cache_similarity_threshold: float = Field(default=0.82, ge=-1, le=1)
    cache_ttl_seconds: int = Field(default=86400, ge=60, le=2592000)
    cache_scan_limit: int = Field(default=2000, ge=1, le=20000)
    demo_mode: bool = True
    app_access_token: Optional[str] = None
    rate_limit_requests: int = Field(default=120, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    rate_limit_client_capacity: int = Field(default=10000, ge=100, le=100000)
    request_body_max_bytes: int = Field(default=1_000_000, ge=1024, le=20_000_000)
    db_pool_size: int = Field(default=5, ge=1, le=50)
    db_max_overflow: int = Field(default=5, ge=0, le=100)
    db_pool_timeout_seconds: int = Field(default=30, ge=1, le=300)
    db_pool_recycle_seconds: int = Field(default=1800, ge=60, le=86400)
    llm_provider: Literal["demo", "openai"] = "demo"
    embedding_provider: Literal["demo", "openai"] = "demo"
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = Field(default=1536, ge=1, le=3072)
    provider_timeout_seconds: float = Field(default=30, gt=0, le=180)
    llm_input_cost_per_million: Optional[float] = Field(default=None, ge=0)
    llm_output_cost_per_million: Optional[float] = Field(default=None, ge=0)
    estimated_llm_call_cost_usd: float = Field(default=0.002, ge=0)
    openai_base_url_allowed_hosts: list[str] = Field(default_factory=lambda: ["api.openai.com"])

    @field_validator("database_ssl_mode", mode="before")
    @classmethod
    def empty_ssl_mode_is_unset(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_runtime(self):
        if not self.demo_mode:
            if not self.app_access_token:
                raise ValueError("APP_ACCESS_TOKEN is required when DEMO_MODE=false")
            if self.llm_provider == "demo" and self.embedding_provider == "demo":
                raise ValueError("At least one real provider must be configured when DEMO_MODE=false")
        if (self.llm_provider == "openai" or self.embedding_provider == "openai") and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when an OpenAI provider is selected")
        if self.demo_mode and (self.llm_provider != "demo" or self.embedding_provider != "demo"):
            raise ValueError("DEMO_MODE=true cannot make external provider calls; select demo providers")
        if not self.cors_origins.strip():
            raise ValueError("CORS_ORIGINS must include at least one explicit origin")
        parsed_provider_url = urlparse(self.openai_base_url)
        if parsed_provider_url.scheme != "https" or parsed_provider_url.hostname not in self.openai_base_url_allowed_hosts:
            raise ValueError("OPENAI_BASE_URL must use HTTPS and an explicitly allowed host")
        if self.app_access_token and len(self.app_access_token) < 32:
            raise ValueError("APP_ACCESS_TOKEN must contain at least 32 characters")
        if not self.demo_mode and self.database_url.startswith("sqlite"):
            raise ValueError("DATABASE_URL must use PostgreSQL when DEMO_MODE=false")
        return self

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
