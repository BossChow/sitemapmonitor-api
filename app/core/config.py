from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/sitemap_monitor"
    redis_url: str = "redis://localhost:6379/0"
    scheduler_batch_size: int = 100
    sitemap_fetch_timeout_seconds: float = 30.0
    max_sitemap_depth: int = 5
    max_sitemap_files: int = 200

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

