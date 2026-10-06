from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import backtests, bars, health
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(bars.router, prefix=settings.api_v1_prefix)
    app.include_router(backtests.router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
