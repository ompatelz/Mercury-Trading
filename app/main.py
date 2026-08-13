from fastapi import FastAPI

from app.api.routes import (
    agent_versions,
    backtests,
    campaigns,
    dashboard,
    evals,
    evolution,
    health,
    live,
    market_data,
    memory,
    paper_trading,
    regimes,
    research,
    research_artifacts,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)
    app.include_router(health.router)
    app.include_router(live.router)
    app.include_router(market_data.router)
    app.include_router(backtests.router)
    app.include_router(research.router)
    app.include_router(research_artifacts.router)
    app.include_router(memory.router)
    app.include_router(regimes.router)
    app.include_router(evals.router)
    app.include_router(agent_versions.router)
    app.include_router(campaigns.router)
    app.include_router(dashboard.router)
    app.include_router(evolution.router)
    app.include_router(paper_trading.router)
    return app


app = create_app()
