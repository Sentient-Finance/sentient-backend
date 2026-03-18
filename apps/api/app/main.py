import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from apps.api.limiter import limiter
from apps.api.v1.routes.main import router as v1_router
from libs.core.config import get_settings
from libs.db.session import get_engine

logger = logging.getLogger(__name__)

_DB_KEEPALIVE_INTERVAL = 300  # 5 minutes


def _ping_db() -> None:
    """Sync helper — run SELECT 1 to keep the connection pool alive."""
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


async def _db_keepalive():
    while True:
        await asyncio.sleep(_DB_KEEPALIVE_INTERVAL)
        try:
            # Run sync SQLAlchemy call off the event loop thread
            await asyncio.to_thread(_ping_db)
            logger.debug("db keepalive ok")
        except Exception as exc:
            logger.warning("db keepalive failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    task = asyncio.create_task(_db_keepalive())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="sentient-backend-api",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["content-type", "authorization", "x-requested-with"],
    )

    @app.get("/health", tags=["meta"])
    def health_root():
        return {"ok": True, "service": "api"}

    app.include_router(v1_router, prefix="/api/v1")

    return app


app = create_app()
