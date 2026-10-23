"""Test configuration.

Integration tests need a PostgreSQL database with pgvector, e.g.:
    createdb helpdesk_test
    TEST_DATABASE_URL=postgresql+asyncpg://helpdesk:helpdesk@localhost:5432/helpdesk_test pytest

They are skipped automatically if the database is unreachable. Unit tests always run.
"""
import os

os.environ.setdefault("TEST_DATABASE_URL", "postgresql+asyncpg://helpdesk:helpdesk@localhost:5432/helpdesk_test")
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["LLM_PROVIDER"] = "mock"
os.environ["OPENAI_API_KEY"] = ""
os.environ["INLINE_JOBS"] = "true"
os.environ["RATE_LIMIT_PER_MINUTE"] = "1000"
os.environ["UPLOAD_DIR"] = "./storage/test_uploads"
os.environ["FIRST_ADMIN_EMAIL"] = "admin@test.edu"
os.environ["FIRST_ADMIN_PASSWORD"] = "Admin@12345"
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
