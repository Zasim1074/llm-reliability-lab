from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./llm_reliability.db"
    cors_origins: str = "http://localhost:3000"
    cache_similarity_threshold: float = 0.82
    cache_ttl_seconds: int = 86400
    demo_mode: bool = True

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
