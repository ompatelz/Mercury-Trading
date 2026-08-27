import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.governance.service import DecisionService
from app.market_data.repository import MarketDataRepository
from app.models.production_simulation import ProductionSimulation
from app.paper_trading.schemas import PaperTradingSessionCreateRequest
from app.paper_trading.service import PaperTradingService
from app.production_simulation.schemas import ProductionSimulationCreateRequest


class ProductionSimulationService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_and_run(self, request: ProductionSimulationCreateRequest) -> ProductionSimulation:
        cadence = request.cadence_days or request.deployment_window_days
        simulation = ProductionSimulation(
            universe=[s.upper() for s in request.universe],
            start_date=request.start_date,
            end_date=request.end_date,
            research_window_days=request.research_window_days,
            deployment_window_days=request.deployment_window_days,
            cadence_days=cadence,
            initial_capital=request.initial_capital,
            execution_model={"mode": "SHADOW", **request.execution},
            data_versions=request.data_versions,
            strategy_versions=[],
            configuration=request.model_dump(mode="json"),
            status="RUNNING",
            timeline=[],
            metrics={},
        )
        self.session.add(simulation)
        self.session.flush()
        started = time.perf_counter()
        capital = request.initial_capital
        cursor = request.start_date
        champion = self._select_candidate(request, request.strategy_version, request.start_date)
        lifecycle: list[dict[str, Any]] = [
            {
                "version": champion["version"],
                "state": "PROMOTED",
                "at": request.start_date.isoformat(),
            }
        ]
        try:
            while cursor < request.end_date:
                research_end = cursor + timedelta(days=request.research_window_days)
                deploy_start = research_end
                deploy_end = min(
                    deploy_start + timedelta(days=request.deployment_window_days), request.end_date
                )
                if deploy_end <= deploy_start:
                    break
                bars = MarketDataRepository(self.session).list_bars(
                    symbol=request.universe[0], interval="1d", start=cursor, end=deploy_end
                )
                if not bars:
                    raise ValueError(
                        f"no market bars found for {request.universe[0]} through {deploy_end}"
                    )
                selected = self._select_candidate(request, champion["version"], research_end)
                previous = champion
                champion = selected
                expected = {
                    "sharpe_ratio": float(champion.get("expected_sharpe", 0.0)),
                    "source": "research_window_only",
                    "as_of": research_end.isoformat(),
                }
                paper = PaperTradingService(self.session).create_session(
                    PaperTradingSessionCreateRequest(
                        symbol=request.universe[0],
                        start=cursor,
                        end=deploy_end,
                        initial_cash=capital,
                        strategy_parameters=champion["parameters"],
                        execution_mode="PAPER",
                        **{
                            k: v
                            for k, v in request.execution.items()
                            if k
                            in {"commission_bps", "slippage_bps", "latency_bars", "execution_model"}
                        },
                    )
                )
                realized = dict(paper.metrics)
                ending = float(realized.get("ending_equity", capital))
                flags: list[str] = []
                if float(realized.get("max_drawdown", 0.0)) > request.max_drawdown:
                    flags.append("DRAWDOWN_EXCEEDS_EXPECTATION")
                event = {
                    "research_start": cursor.isoformat(),
                    "research_end": research_end.isoformat(),
                    "deployment_start": deploy_start.isoformat(),
                    "deployment_end": deploy_end.isoformat(),
                    "strategy_version": champion["version"],
                    "parameters": dict(champion["parameters"]),
                    "portfolio_weights": dict(request.portfolio_weights),
                    "expected": expected,
                    "realized": realized,
                    "degradation": {
                        "sharpe_delta": float(realized.get("sharpe_ratio", 0.0)),
                        "return_delta": ending / capital - 1.0,
                    },
                    "lifecycle": "ACTIVE",
                    "governance_decision": (
                        f"simulation:{simulation.id}:{len(simulation.timeline) + 1}"
                    ),
                    "flags": flags,
                    "paper_session_id": str(paper.id),
                    "counterfactual": {
                        "previous_champion": previous["version"],
                        "previous_champion_return": ending / capital - 1.0,
                        "decision_uses_counterfactual": False,
                    },
                }
                if champion["version"] != previous["version"]:
                    lifecycle.extend(
                        [
                            {
                                "version": previous["version"],
                                "state": "RETIRED",
                                "at": research_end.isoformat(),
                            },
                            {
                                "version": champion["version"],
                                "state": "PROMOTED",
                                "at": research_end.isoformat(),
                            },
                        ]
                    )
                    event["lifecycle"] = "REPLACED"
                lifecycle.append(
                    {
                        "version": champion["version"],
                        "state": "ACTIVE",
                        "at": deploy_start.isoformat(),
                    }
                )
                DecisionService(self.session).record(
                    decision_type="SHADOW_DEPLOYMENT",
                    outcome="ACTIVE",
                    actor="ProductionSimulationService",
                    reason="Frozen strategy entered a paper-only forward replay window.",
                    correlation_id=f"simulation:{simulation.id}:{len(simulation.timeline) + 1}",
                    inputs={
                        "research_end": research_end.isoformat(),
                        "deployment_end": deploy_end.isoformat(),
                    },
                    metrics={"expected": expected, "realized": realized},
                    provenance={
                        "paper_session_id": str(paper.id),
                        "data_versions": request.data_versions,
                    },
                    versions={"simulation": "v1", "execution_mode": "SHADOW->PAPER"},
                )
                simulation.timeline = [*simulation.timeline, event]
                simulation.strategy_versions = list(
                    dict.fromkeys([*simulation.strategy_versions, champion["version"]])
                )
                capital = ending
                if flags and request.kill_action == "STOP":
                    event["kill_action"] = "STOP"
                    break
                cursor += timedelta(days=cadence)
            simulation.status = "COMPLETED"
            simulation.metrics = self._metrics(
                simulation.timeline, started, capital, request.initial_capital
            )
            simulation.metrics["champion_lifecycle"] = lifecycle
            simulation.ended_at = datetime.now(UTC)
        except Exception as exc:
            simulation.status = "FAILED"
            simulation.error_message = str(exc)
            simulation.ended_at = datetime.now(UTC)
            raise
        self.session.flush()
        self.session.refresh(simulation)
        return simulation

    def get(self, simulation_id: UUID) -> ProductionSimulation | None:
        return self.session.get(ProductionSimulation, simulation_id)

    @staticmethod
    def _select_candidate(
        request: ProductionSimulationCreateRequest,
        current_version: str,
        as_of: date,
    ) -> dict[str, Any]:
        candidates = [
            {"version": request.strategy_version, "parameters": request.strategy_parameters}
        ] + request.candidates
        eligible = [
            item
            for item in candidates
            if item.get("promoted", True)
            and date.fromisoformat(str(item.get("as_of", "0001-01-01"))) <= as_of
        ]
        return max(
            eligible,
            key=lambda item: (
                float(item.get("expected_sharpe", 0.0)),
                str(item["version"]) == current_version,
                str(item["version"]),
            ),
        )

    @staticmethod
    def _metrics(
        timeline: list[dict[str, Any]], started: float, ending: float, initial: float
    ) -> dict[str, Any]:
        return {
            "research_cycles": len(timeline),
            "deployments": len(timeline),
            "ending_equity": ending,
            "pnl": ending - initial,
            "events_processed": sum(int(x["realized"].get("market_events", 0)) for x in timeline),
            "strategy_changes": max(0, len({x["strategy_version"] for x in timeline}) - 1),
            "kill_events": sum(bool(x["flags"]) for x in timeline),
            "runtime_ms": round((time.perf_counter() - started) * 1000, 6),
            "expected_vs_realized_degradation": [x["degradation"] for x in timeline],
        }
