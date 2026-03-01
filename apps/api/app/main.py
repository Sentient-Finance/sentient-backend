from contextlib import asynccontextmanager

from fastapi import FastAPI

from apps.api.v1.routes.main import router as v1_router
from apps.api.v1.routes.vaults import router as vaults_router
from libs.core.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = get_settings()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="sentient-backend-api",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Root-level health — useful for load-balancer / Docker healthchecks
    @app.get("/health", tags=["meta"])
    def health_root():
        return {"ok": True, "service": "api"}

    app.include_router(v1_router, prefix="/api/v1")
    app.include_router(vaults_router, prefix="/api/v1")

    return app


app = create_app()

