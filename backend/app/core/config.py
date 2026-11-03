"""Application settings, loaded from environment variables / .env file."""
import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # `neon deploy` writes DATABASE_URL and the object-storage keys to ../.env.local (repo root).
    # Later files override earlier ones, and real environment variables override both.
    model_config = SettingsConfigDict(env_file=(".env", "../.env.local"), env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "College AI Help Desk"
    COLLEGE_NAME: str = "ABC Engineering College"
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174", "http://localhost:8080"])

    # --- Security ---
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    JWT_ALGORITHM: str = "HS256"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://helpdesk:helpdesk@localhost:5432/helpdesk"

    # --- Object storage (Neon / any S3-compatible). Empty S3_BUCKET = keep uploads on local disk. ---
    S3_BUCKET: str = ""
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_REGION: str = "auto"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- LLM ---
    # LLM_PROVIDER: "openai" for real answers, "mock" for offline development/testing.
    LLM_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str | None = None
    CHAT_MODEL: str = "gpt-4o-mini"
    CHAT_MODEL_FALLBACK: str = "gpt-4o"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 700

    # --- RAG ---
    CHUNK_SIZE_TOKENS: int = 600
    CHUNK_OVERLAP_TOKENS: int = 100
    RETRIEVAL_CANDIDATES: int = 20
    RETRIEVAL_TOP_K: int = 5
    MIN_RELEVANCE_SCORE: float = 0.30   # below this → "I don't know" + offer ticket
    FAQ_MATCH_THRESHOLD: float = 0.86   # cosine similarity for direct FAQ answers
    HISTORY_TURNS: int = 6
    CURRENT_ACADEMIC_YEAR: str = "2026-27"

    # --- Limits ---
    RATE_LIMIT_PER_MINUTE: int = 20
    MAX_MESSAGE_CHARS: int = 1000
    MAX_UPLOAD_MB: int = 25
    UPLOAD_DIR: Path = Path("./storage/uploads")
    CHAT_RETENTION_DAYS: int = 365

    # --- Email (ticket alerts) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "helpdesk@college.edu"
    SMTP_TLS: bool = True

    # --- Seed admin ---
    FIRST_ADMIN_EMAIL: str = "admin@college.edu"
    FIRST_ADMIN_PASSWORD: str = "Admin@12345"

    # --- Monitoring ---
    SENTRY_DSN: str = ""

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_origins(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v

    @field_validator("DATABASE_URL")
    @classmethod
    def asyncpg_url(cls, v: str) -> str:
        """Accept a plain libpq-style URL (as Neon provides) and make it asyncpg-ready:
        postgresql:// → postgresql+asyncpg://, sslmode=… → ssl=…, and drop channel_binding."""
        parts = urlsplit(v)
        if parts.scheme in ("postgres", "postgresql"):
            parts = parts._replace(scheme="postgresql+asyncpg")
        query = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            if key == "channel_binding":
                continue
            query.append(("ssl" if key == "sslmode" else key, val))
        return urlunsplit(parts._replace(query=urlencode(query)))

    @property
    def is_mock_llm(self) -> bool:
        return self.LLM_PROVIDER == "mock" or not self.OPENAI_API_KEY

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg").replace("ssl=", "sslmode=")

    @property
    def use_s3(self) -> bool:
        return bool(self.S3_BUCKET and self.AWS_ENDPOINT_URL_S3)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
