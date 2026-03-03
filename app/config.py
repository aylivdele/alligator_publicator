import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    GRAPH_API_CLIENT_ID: str
    GRAPH_API_CLIENT_SECRET: str
    GRAPH_API_REDIRECT_URI: str

    STORAGE_ENDPOINT: str
    STORAGE_ACCESS_KEY: str
    STORAGE_SECRET_KEY: str
    STORAGE_BUCKET: str

    DATABASE_URL: str

    SECRET_KEY: str = "change-me-in-production"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin"

    VIEWS_MAX_AGE_HOURS: int = 48
    VIEWS_REFRESH_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

settings = Settings() # type: ignore[call-arg]