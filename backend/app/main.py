"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.redis import close_redis

setup_logging()
log = logging.getLogger("app")

if settings.SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(dsn=settings.SENTRY_DSN, environment=settings.ENVIRONMENT, traces_sample_rate=0.1)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Starting %s (LLM: %s)", settings.APP_NAME, "mock" if settings.is_mock_llm else settings.CHAT_MODEL)
    if settings.ENVIRONMENT == "production" and settings.SECRET_KEY.startswith("change-me"):
        log.error("SECRET_KEY is still the default value. Set a strong SECRET_KEY in production!")
    yield
    await close_redis()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
    docs_url=f"{settings.API_PREFIX}/docs",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    # Return the first readable message so the UI can show it directly.
    errors = exc.errors()
    first = errors[0] if errors else {}
    msg = first.get("msg", "Invalid request").replace("Value error, ", "")
    field = ".".join(str(x) for x in first.get("loc", [])[1:])
    return JSONResponse(status_code=422, content={"detail": f"{field}: {msg}" if field else msg, "errors": jsonable(errors)})


def jsonable(errors):
    return [{k: (str(v) if k == "ctx" else v) for k, v in e.items() if k != "input"} for e in errors]


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/")
async def root():
    return {"name": settings.APP_NAME, "docs": f"{settings.API_PREFIX}/docs"}
