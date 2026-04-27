import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.api import api_router
from app.scheduler.jobs import setup_scheduler
from app.config import settings

log = structlog.get_logger()

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting Betting Creator Tracker API")
    # Run lightweight migrations for new columns
    _run_migrations()
    setup_scheduler()
    yield
    log.info("Shutting down")
    from app.posthog_client import posthog_client
    if posthog_client:
        posthog_client.flush()


def _run_migrations():
    """Add any missing columns to existing tables."""
    from sqlalchemy import text, inspect
    from app.database import engine
    try:
        with engine.connect() as conn:
            inspector = inspect(engine)
            columns = [c["name"] for c in inspector.get_columns("creators")]
            if "profile_image_url" not in columns:
                conn.execute(text("ALTER TABLE creators ADD COLUMN profile_image_url VARCHAR"))
                conn.commit()
                log.info("Added profile_image_url column to creators")
    except Exception as e:
        log.warning("Migration check failed (non-fatal)", error=str(e))


# Hide docs in production
is_prod = settings.environment == "production"

app = FastAPI(
    title="Pick Receipts API",
    description="Transparent W/L records for sports betting creators",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json",
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — read allowed origins from env var (comma-separated)
allowed_origins = [o.strip() for o in settings.allowed_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(api_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — never expose stack traces in production."""
    log.error("Unhandled exception", path=request.url.path, error=str(exc))
    if is_prod:
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    # In development, include the error message for debugging
    return JSONResponse(status_code=500, content={"detail": str(exc)})
