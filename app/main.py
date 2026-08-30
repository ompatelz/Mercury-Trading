from collections.abc import Awaitable, Callable
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

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
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    @app.exception_handler(Exception)
    async def unhandled_exception(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "internal server error"},
        )

    @app.middleware("http")
    async def trace_request(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        started = perf_counter()
        content_length = request.headers.get("content-length")
        try:
            request_size = int(content_length) if content_length is not None else 0
        except ValueError:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "invalid content length"},
                headers={"X-Correlation-ID": correlation_id},
            )
        if request_size > settings.max_request_body_bytes:
            response: Response = JSONResponse(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                content={"detail": "request body too large"},
            )
            response.headers["X-Correlation-ID"] = correlation_id
            metrics.record_request(
                request.method,
                response.status_code,
                (perf_counter() - started) * 1000,
            )
            return response
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
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
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
