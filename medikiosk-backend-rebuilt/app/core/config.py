"""
Configuration.

Module 2 of the blueprint: one typed settings object, everything from the
environment, no secret ever written in code. Provider names here are what the
factories in `app.services.*` resolve against — swapping `AI_PROVIDER=mock`
changes which adapter the whole application uses, with no other edit.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # ---------------------------------------------------------------- app --
    ENV: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = True
    APP_NAME: str = "MediKiosk API"
    API_V1_PREFIX: str = "/api/v1"
    SECRET_KEY: str = Field(default="dev-only-change-me", min_length=8)

    # Comma-separated in the env, list here.
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ----------------------------------------------------------- database --
    # asyncpg for the app, psycopg2 for Alembic — see `sync_database_url`.
    DATABASE_URL: str = "postgresql+asyncpg://medikiosk:medikiosk@localhost:5432/medikiosk"
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # --------------------------------------------------------------- auth --
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 7
    BCRYPT_ROUNDS: int = 12
    LOGIN_RATE_LIMIT: str = "8/minute"

    # ---------------------------------------------------------- providers --
    AI_PROVIDER: Literal["gemini", "mock"] = "mock"
    OCR_PROVIDER: Literal["tesseract", "textract", "mock"] = "mock"
    STORAGE_PROVIDER: Literal["local", "s3"] = "local"
    SPEECH_PROVIDER: Literal["browser", "cloud"] = "browser"
    ABDM_PROVIDER: Literal["mock", "real"] = "mock"

    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"
    AI_TIMEOUT_SECONDS: float = 20.0
    AI_MAX_RETRIES: int = 2

    TESSERACT_CMD: str | None = None
    TESSERACT_LANGS: str = "eng+hin+kan"

    # ------------------------------------------------------------ storage --
    LOCAL_STORAGE_DIR: str = "./storage"
    S3_BUCKET: str | None = None
    S3_REGION: str = "ap-south-1"
    # Omitted on ECS/App Runner — the task role supplies credentials instead.
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    S3_SIGNED_URL_TTL_SECONDS: int = 300

    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    ALLOWED_UPLOAD_MIME: list[str] = ["application/pdf", "image/jpeg", "image/png"]

    # --------------------------------------------------------------- demo --
    # Guards POST /admin/seed-demo. Must stay false in production.
    ALLOW_DEMO_SEED: bool = True

    @field_validator("CORS_ORIGINS", "ALLOWED_UPLOAD_MIME", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def _guard_production(self) -> "Settings":
        if self.ENV == "production":
            if self.SECRET_KEY == "dev-only-change-me":
                raise ValueError("SECRET_KEY must be set to a real value in production.")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production.")
            if self.ALLOW_DEMO_SEED:
                raise ValueError("ALLOW_DEMO_SEED must be false in production.")
            if self.AI_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
                raise ValueError("AI_PROVIDER=gemini requires GEMINI_API_KEY.")
            if self.STORAGE_PROVIDER == "s3" and not self.S3_BUCKET:
                raise ValueError("STORAGE_PROVIDER=s3 requires S3_BUCKET.")
        return self

    @property
    def sync_database_url(self) -> str:
        """Alembic runs synchronously; strip the async driver."""
        return self.DATABASE_URL.replace("+asyncpg", "").replace("postgresql://", "postgresql+psycopg2://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
