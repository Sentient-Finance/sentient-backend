from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.v1.routes.main import router as v1_router
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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    def health_root():
        return {
            "ok": True,
            "service": "api",
            "vaults_owner_filter": True,
            "loaded_from": str(__file__),
        }

    app.include_router(v1_router, prefix="/api/v1")

    return app

app = create_app()

