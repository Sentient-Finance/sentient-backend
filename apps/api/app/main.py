import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from apps.api.v1.routes.main import router as v1_router
from libs.core.config import get_settings
from libs.db.session import get_engine

logger = logging.getLogger(__name__)

_DB_KEEPALIVE_INTERVAL = 300  # 5 minutes


async def _db_keepalive():
    while True:
        await asyncio.sleep(_DB_KEEPALIVE_INTERVAL)
        try:
            engine = get_engine()
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.debug("db keepalive ok")
        except Exception as exc:
            logger.warning("db keepalive failed: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = get_settings()
    task = asyncio.create_task(_db_keepalive())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="sentient-backend-api",
        version="0.1.0",
        lifespan=lifespan,
    )

    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health_root():
        return {"ok": True, "service": "api"}

    app.include_router(v1_router, prefix="/api/v1")

    return app

app = create_app()

