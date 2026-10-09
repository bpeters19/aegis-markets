from datetime import date
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")

    app_name: str = "Aegis Markets"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str

    alpaca_api_key_id: str | None = None
    alpaca_api_secret_key: SecretStr | None = None
    alpaca_data_url: str = "https://data.alpaca.markets"
    alpaca_feed: str = "iex"
    alpaca_adjustment: str = "split"

    tiingo_api_key: SecretStr | None = None
    tiingo_base_url: str = "https://api.tiingo.com"
    tiingo_adjusted: bool = True

    cors_origins: list[str] = ["http://localhost:3000"]

    research_lock_date: date = date(2023, 1, 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
