from fastapi import FastAPI

from app.api.routes import backtests, health, market_data, research
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health.router)
    app.include_router(market_data.router)
    app.include_router(backtests.router)
    app.include_router(research.router)
    return app


app = create_app()
