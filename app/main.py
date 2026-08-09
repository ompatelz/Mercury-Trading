from fastapi import FastAPI

from app.api.routes import agent_versions, backtests, evals, health, market_data, memory, research
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health.router)
    app.include_router(market_data.router)
    app.include_router(backtests.router)
    app.include_router(research.router)
    app.include_router(memory.router)
    app.include_router(evals.router)
    app.include_router(agent_versions.router)
    return app


app = create_app()
