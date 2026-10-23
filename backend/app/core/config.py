"""Application settings, loaded from environment variables / .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "College AI Help Desk"
    COLLEGE_NAME: str = "ABC Engineering College"
    ENVIRONMENT: str = "development"  # development | production
    DEBUG: bool = False
    API_PREFIX: str = "/api"
    CORS_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:5173", "http://localhost:5174", "http://localhost:8080"])

    # --- Security ---
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8
    JWT_ALGORITHM: str = "HS256"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://helpdesk:helpdesk@localhost:5432/helpdesk"

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
        if isinstance(v, str) and not v.startswith("["):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_mock_llm(self) -> bool:
        return self.LLM_PROVIDER == "mock" or not self.OPENAI_API_KEY

    @property
    def sync_database_url(self) -> str:
        return self.DATABASE_URL.replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
