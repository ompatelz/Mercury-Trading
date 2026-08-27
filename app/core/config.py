from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Mercury"
    environment: str = "local"
    debug: bool = False
    database_url: str = Field(
        default="postgresql+psycopg://mercury:mercury@localhost:5432/mercury",
        validation_alias="DATABASE_URL",
    )
    yahoo_auto_adjust: bool = Field(default=False, validation_alias="YAHOO_AUTO_ADJUST")
    live_market_data_provider: str = Field(
        default="yahoo", validation_alias="LIVE_MARKET_DATA_PROVIDER"
    )
    live_market_data_poll_seconds: float = Field(
        default=30.0, validation_alias="LIVE_MARKET_DATA_POLL_SECONDS"
    )
    execution_mode: str = Field(default="PAPER", validation_alias="EXECUTION_MODE")
    backtest_engine: str = Field(default="python", validation_alias="BACKTEST_ENGINE")
    routing_policy: str = Field(default="balanced", validation_alias="ROUTING_POLICY")
    allow_model_fallback: bool = Field(default=True, validation_alias="ALLOW_MODEL_FALLBACK")
    data_storage_root: Path = Field(
        default=Path(".mercury-data"), validation_alias="DATA_STORAGE_ROOT"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
