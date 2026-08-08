from functools import lru_cache

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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
