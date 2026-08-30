from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status

from app.api.routes import (
    agent_versions,
    backtests,
    campaigns,
    dashboard,
    data,
    decisions,
    evals,
    evolution,
    factor_research,
    health,
    live,
    market_data,
    memory,
    ml_research,
    observability,
    paper_trading,
    production_simulations,
    regimes,
    research,
    research_artifacts,
    strategies,
    strategy_health,
    stress_tests,
)
from app.core.config import get_settings
from app.observability.metrics import metrics


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    @app.middleware("http")
    async def trace_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            metrics.record_request(
                request.method,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                (perf_counter() - started) * 1000,
            )
            raise

        response.headers["X-Correlation-ID"] = correlation_id
        metrics.record_request(
            request.method, response.status_code, (perf_counter() - started) * 1000
        )
        return response

    app.include_router(health.router)
    app.include_router(observability.router)
    app.include_router(live.router)
    app.include_router(market_data.router)
    app.include_router(data.router)
    app.include_router(factor_research.router)
    app.include_router(ml_research.router)
    app.include_router(decisions.router)
    app.include_router(backtests.router)
    app.include_router(stress_tests.router)
    app.include_router(strategies.router)
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
    app.include_router(strategy_health.router)
    app.include_router(production_simulations.router)
    return app


app = create_app()
