from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dashboard.schemas import (
    CampaignDashboardResponse,
    ComponentHealth,
    DashboardMetric,
    DashboardOverviewResponse,
    ExperimentDetailResponse,
    ExperimentListItem,
    ExperimentListResponse,
    PaperTradingDashboardResponse,
    RecentActivityItem,
    StrategyComparisonResponse,
    StrategyLineageEdge,
    StrategyLineageNode,
    StrategyLineageResponse,
    TradeChartPoint,
)
from app.models.campaign import CampaignExperiment, CampaignJob, ResearchCampaign, StrategyRanking
from app.models.evolution import EvolutionRun, StrategyCandidate
from app.models.experiment import BacktestTradeRecord, Experiment, ResearchExperiment
from app.models.memory import ResearchMemoryLesson
from app.models.paper_trading import PaperFillRecord, PaperOrderRecord, PaperTradingSession


class DashboardService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def overview(self) -> DashboardOverviewResponse:
        experiments = list(self.session.scalars(select(Experiment)).all())
        campaign_experiments = list(self.session.scalars(select(CampaignExperiment)).all())
        campaigns = list(self.session.scalars(select(ResearchCampaign)).all())
        candidates = list(self.session.scalars(select(StrategyCandidate)).all())
        sessions = list(self.session.scalars(select(PaperTradingSession)).all())

        completed = [item for item in campaign_experiments if item.status == "completed"]
        rejected = [
            item
            for item in campaign_experiments
            if item.status in {"rejected", "failed"} or bool(item.risk_flags)
        ]
        champions = [item for item in candidates if item.promotion_status == "promote"]
        sharpe_values = [
            _metric_float(item.metrics, "sharpe_ratio", "sharpe") for item in experiments
        ]
        drawdowns = [_metric_float(item.metrics, "max_drawdown") for item in experiments]

        success_rate = len(completed) / len(campaign_experiments) if campaign_experiments else None
        metrics = [
            DashboardMetric(label="Experiments Run", value=len(experiments)),
            DashboardMetric(
                label="Active Campaigns",
                value=len([item for item in campaigns if item.status in {"created", "running"}]),
            ),
            DashboardMetric(label="Successful Strategies", value=len(completed)),
            DashboardMetric(label="Rejected Strategies", value=len(rejected)),
            DashboardMetric(label="Champion Strategies", value=len(champions)),
            DashboardMetric(label="Average OOS Sharpe", value=_average(sharpe_values)),
            DashboardMetric(label="Average Max Drawdown", value=_average(drawdowns)),
            DashboardMetric(label="Research Success Rate", value=success_rate, unit="ratio"),
            DashboardMetric(label="Paper Trading Sessions", value=len(sessions)),
        ]
        return DashboardOverviewResponse(
            metrics=metrics,
            recent_activity=self._recent_activity(),
            system_health=self._system_health(),
        )

    def list_experiments(
        self,
        *,
        strategy_family: str | None,
        symbol: str | None,
        campaign_id: UUID | None,
        status: str | None,
        regime: str | None,
        risk_flag: str | None,
        agent_version: str | None,
        limit: int,
        offset: int,
    ) -> ExperimentListResponse:
        stmt = select(Experiment)
        if strategy_family:
            stmt = stmt.where(Experiment.strategy_name == strategy_family)
        if symbol:
            stmt = stmt.where(Experiment.symbol == symbol.upper())
        if status:
            stmt = stmt.where(Experiment.status == status)

        experiments = list(
            self.session.scalars(
                stmt.order_by(Experiment.created_at.desc()).limit(limit).offset(offset)
            )
        )
        items = [
            self._experiment_item(item)
            for item in experiments
            if self._matches_experiment_filters(
                item,
                campaign_id=campaign_id,
                regime=regime,
                risk_flag=risk_flag,
                agent_version=agent_version,
            )
        ]
        total = self.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        return ExperimentListResponse(items=items, total=total, limit=limit, offset=offset)

    def experiment_detail(self, experiment_id: UUID) -> ExperimentDetailResponse | None:
        experiment = self.session.get(Experiment, experiment_id)
        if experiment is None:
            return None
        campaign_experiment = self.session.scalar(
            select(CampaignExperiment).where(CampaignExperiment.experiment_id == experiment_id)
        )
        research_experiment = self.session.scalar(
            select(ResearchExperiment).where(
                ResearchExperiment.backtest_experiment_id == experiment_id
            )
        )
        memory_lessons = list(
            self.session.scalars(
                select(ResearchMemoryLesson)
                .where(ResearchMemoryLesson.backtest_experiment_id == experiment_id)
                .order_by(ResearchMemoryLesson.created_at.desc())
                .limit(10)
            )
        )
        trades = list(
            self.session.scalars(
                select(BacktestTradeRecord)
                .where(BacktestTradeRecord.experiment_id == experiment_id)
                .order_by(BacktestTradeRecord.timestamp, BacktestTradeRecord.id)
                .limit(500)
            )
        )
        regime_performance = _dict_value(experiment.run_metadata, "regime_performance")
        return ExperimentDetailResponse(
            experiment=self._experiment_item(experiment),
            parameters=experiment.parameters,
            transaction_cost_bps=experiment.transaction_cost_bps,
            slippage_bps=experiment.slippage_bps,
            research_context={
                "hypothesis": (
                    campaign_experiment.hypothesis
                    if campaign_experiment is not None
                    else (research_experiment.hypothesis if research_experiment is not None else {})
                ),
                "strategy_definition": (
                    research_experiment.strategy if research_experiment is not None else {}
                ),
                "campaign_id": str(campaign_experiment.campaign_id)
                if campaign_experiment is not None
                else None,
                "agent_version": _metadata_version(research_experiment, "agent"),
                "workflow_version": _metadata_version(research_experiment, "workflow"),
                "dataset_period": {
                    "start": experiment.start_date.isoformat(),
                    "end": experiment.end_date.isoformat(),
                    "interval": experiment.data_interval,
                },
            },
            performance=experiment.metrics,
            regime_performance=regime_performance,
            regime_weaknesses=_regime_weaknesses(regime_performance),
            memory_lessons=[
                {
                    "id": str(item.id),
                    "hypothesis": item.hypothesis,
                    "critic_summary": item.critic_summary,
                    "observations": item.observations,
                    "failure_reasons": item.failure_reasons,
                    "confidence": item.confidence,
                }
                for item in memory_lessons
            ],
            trades=[
                TradeChartPoint(
                    timestamp=trade.timestamp,
                    side=trade.side,
                    price=float(trade.price),
                    quantity=float(trade.quantity),
                    realized_pnl=(
                        float(trade.realized_pnl) if trade.realized_pnl is not None else None
                    ),
                )
                for trade in trades
            ],
        )

    def campaign_detail(self, campaign_id: UUID) -> CampaignDashboardResponse | None:
        campaign = self.session.get(ResearchCampaign, campaign_id)
        if campaign is None:
            return None
        experiments = list(
            self.session.scalars(
                select(CampaignExperiment)
                .where(CampaignExperiment.campaign_id == campaign_id)
                .order_by(CampaignExperiment.created_at)
            )
        )
        rankings = list(
            self.session.scalars(
                select(StrategyRanking)
                .where(StrategyRanking.campaign_id == campaign_id)
                .order_by(StrategyRanking.rank)
                .limit(5)
            )
        )
        jobs = list(
            self.session.scalars(
                select(CampaignJob)
                .where(CampaignJob.campaign_id == campaign_id)
                .order_by(CampaignJob.created_at)
            )
        )
        top_candidates = [
            {
                "campaign_experiment_id": str(item.campaign_experiment_id),
                "rank": item.rank,
                "score": item.score,
                "reason": item.ranking_reason,
                "risk_flags": item.risk_flags,
            }
            for item in rankings
        ]
        return CampaignDashboardResponse(
            id=campaign.id,
            objective=campaign.objective,
            status=campaign.status,
            constraints=campaign.constraints,
            budget=campaign.budget,
            budget_used=campaign.budget_used,
            rounds_completed=len([job for job in jobs if job.status == "SUCCEEDED"]),
            hypotheses_explored=len(campaign.generated_hypotheses),
            experiment_count=len(experiments),
            rejected_strategy_count=len(campaign.rejected_strategies),
            top_candidates=top_candidates,
            current_best_candidate=top_candidates[0] if top_candidates else None,
            stopping_condition=campaign.stop_conditions,
            progress=[
                {
                    "timestamp": item.created_at.isoformat(),
                    "status": item.status,
                    "strategy_family": item.strategy_family,
                    "symbol": item.symbol,
                    "score": _metric_float(item.metrics, "sharpe_ratio", "sharpe"),
                    "risk_flags": item.risk_flags,
                }
                for item in experiments
            ],
        )

    def strategy_lineage(self, strategy_id: UUID) -> StrategyLineageResponse | None:
        strategy = self.session.get(StrategyCandidate, strategy_id)
        if strategy is None:
            return None
        candidates = list(
            self.session.scalars(
                select(StrategyCandidate)
                .where(StrategyCandidate.evolution_run_id == strategy.evolution_run_id)
                .order_by(StrategyCandidate.generation, StrategyCandidate.created_at)
            )
        )
        nodes = [
            StrategyLineageNode(
                id=item.id,
                parent_strategy_ids=item.parent_strategy_ids,
                generation=item.generation,
                fitness=item.fitness,
                status=item.status,
                mutation_type=item.mutation_type,
                changed_fields=item.changed_fields,
                promotion_status=item.promotion_status,
                rejection_reason=item.rejection_reason,
            )
            for item in candidates
        ]
        known_ids = {str(item.id) for item in candidates}
        edges = [
            StrategyLineageEdge(parent_id=parent_id, child_id=item.id)
            for item in candidates
            for parent_id in item.parent_strategy_ids
            if parent_id in known_ids
        ]
        return StrategyLineageResponse(
            root_strategy_id=strategy.id,
            evolution_run_id=strategy.evolution_run_id,
            nodes=nodes,
            edges=edges,
        )

    def compare_strategies(
        self, champion_id: UUID, challenger_id: UUID
    ) -> StrategyComparisonResponse | None:
        champion = self.session.get(StrategyCandidate, champion_id)
        challenger = self.session.get(StrategyCandidate, challenger_id)
        if champion is None or challenger is None:
            return None
        run = self.session.get(EvolutionRun, champion.evolution_run_id)
        challenger_promoted = challenger.promotion_status == "promote"
        reason = (
            "Challenger meets promotion status."
            if challenger_promoted
            else challenger.rejection_reason or "Challenger did not satisfy promotion criteria."
        )
        return StrategyComparisonResponse(
            champion_id=champion.id,
            challenger_id=challenger.id,
            metrics={
                "champion": champion.fitness,
                "challenger": challenger.fitness,
            },
            regime_robustness={
                "champion": champion.regime_performance,
                "challenger": challenger.regime_performance,
            },
            overfitting_flags=_overfitting_flags(challenger),
            decision="promote" if challenger_promoted else "reject",
            reason=reason,
            promotion_criteria=(run.settings if run is not None else {}),
        )

    def paper_session(self, session_id: UUID) -> PaperTradingDashboardResponse | None:
        paper_session = self.session.get(PaperTradingSession, session_id)
        if paper_session is None:
            return None
        orders = list(
            self.session.scalars(
                select(PaperOrderRecord)
                .where(PaperOrderRecord.session_id == session_id)
                .order_by(PaperOrderRecord.created_at.desc())
                .limit(20)
            )
        )
        fills = list(
            self.session.scalars(
                select(PaperFillRecord)
                .where(PaperFillRecord.session_id == session_id)
                .order_by(PaperFillRecord.timestamp.desc())
                .limit(20)
            )
        )
        portfolio = paper_session.final_portfolio
        equity = _maybe_float(portfolio.get("equity"))
        cash = _maybe_float(portfolio.get("cash"))
        initial_cash = float(paper_session.initial_cash)
        return PaperTradingDashboardResponse(
            id=paper_session.id,
            strategy_name=paper_session.strategy_name,
            symbol=paper_session.symbol,
            interval=paper_session.interval,
            execution_mode=paper_session.execution_mode,
            status=paper_session.status,
            cash=cash,
            equity=equity,
            pnl=equity - initial_cash if equity is not None else None,
            positions=_dict_value(portfolio, "positions"),
            metrics=paper_session.metrics,
            recent_orders=[_order_payload(item) for item in orders],
            recent_fills=[_fill_payload(item) for item in fills],
            rejected_orders=[_order_payload(item) for item in orders if item.status == "REJECTED"],
            system_health=[
                ComponentHealth(
                    component="Paper Broker",
                    status=paper_session.status,
                    detail="Session persisted",
                ),
                ComponentHealth(
                    component="Strategy Runner",
                    status=paper_session.execution_mode,
                    detail=paper_session.strategy_name,
                ),
            ],
        )

    def _recent_activity(self) -> list[RecentActivityItem]:
        research = [
            RecentActivityItem(
                id=item.id,
                kind="research_experiment",
                title=item.objective,
                status=item.status,
                created_at=item.created_at,
                metadata={"symbol": item.symbol, "interval": item.interval},
            )
            for item in self.session.scalars(
                select(ResearchExperiment).order_by(ResearchExperiment.created_at.desc()).limit(5)
            )
        ]
        campaigns = [
            RecentActivityItem(
                id=item.id,
                kind="campaign",
                title=item.objective,
                status=item.status,
                created_at=item.created_at,
                metadata={"symbols": item.symbols, "budget_used": item.budget_used},
            )
            for item in self.session.scalars(
                select(ResearchCampaign).order_by(ResearchCampaign.created_at.desc()).limit(5)
            )
        ]
        return sorted([*research, *campaigns], key=lambda item: item.created_at, reverse=True)[:8]

    def _system_health(self) -> list[ComponentHealth]:
        table_checks: list[tuple[str, type[Any]]] = [
            ("Database", Experiment),
            ("Research Campaigns", ResearchCampaign),
            ("Paper Broker", PaperTradingSession),
            ("Strategy Evolution", EvolutionRun),
        ]
        health = [ComponentHealth(component="API", status="ok", detail="Dashboard API reachable")]
        for label, model in table_checks:
            count = self.session.scalar(select(func.count()).select_from(model)) or 0
            health.append(ComponentHealth(component=label, status="ok", detail=f"{count} records"))
        return health

    def _experiment_item(self, experiment: Experiment) -> ExperimentListItem:
        campaign_experiment = self.session.scalar(
            select(CampaignExperiment).where(CampaignExperiment.experiment_id == experiment.id)
        )
        research_experiment = self.session.scalar(
            select(ResearchExperiment).where(
                ResearchExperiment.backtest_experiment_id == experiment.id
            )
        )
        campaign_id = campaign_experiment.campaign_id if campaign_experiment is not None else None
        return ExperimentListItem(
            id=experiment.id,
            strategy_name=experiment.strategy_name,
            symbol=experiment.symbol,
            status=experiment.status,
            start_date=experiment.start_date,
            end_date=experiment.end_date,
            created_at=experiment.created_at,
            metrics=experiment.metrics,
            regime_robustness=_dict_value(experiment.run_metadata, "regime_robustness"),
            campaign_id=campaign_id,
            risk_flags=campaign_experiment.risk_flags if campaign_experiment is not None else [],
            agent_version=_metadata_version(research_experiment, "agent"),
            workflow_version=_metadata_version(research_experiment, "workflow"),
        )

    def _matches_experiment_filters(
        self,
        experiment: Experiment,
        *,
        campaign_id: UUID | None,
        regime: str | None,
        risk_flag: str | None,
        agent_version: str | None,
    ) -> bool:
        item = self._experiment_item(experiment)
        if campaign_id is not None and item.campaign_id != campaign_id:
            return False
        if risk_flag is not None and risk_flag not in item.risk_flags:
            return False
        if agent_version is not None and item.agent_version != agent_version:
            return False
        regime_performance = _dict_value(experiment.run_metadata, "regime_performance")
        return not (regime is not None and regime not in regime_performance)


def _average(values: list[float | None]) -> float | None:
    clean = [item for item in values if item is not None]
    return sum(clean) / len(clean) if clean else None


def _metric_float(metrics: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metrics.get(key)
        parsed = _maybe_float(value)
        if parsed is not None:
            return parsed
    return None


def _maybe_float(value: object) -> float | None:
    if isinstance(value, int | float | Decimal):
        return float(value)
    return None


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _metadata_version(experiment: ResearchExperiment | None, key: str) -> str | None:
    if experiment is None:
        return None
    metadata = experiment.model_metadata if key == "agent" else experiment.workflow_metadata
    version = metadata.get("version") or metadata.get(f"{key}_version")
    return str(version) if version is not None else None


def _regime_weaknesses(regime_performance: dict[str, Any]) -> list[str]:
    weaknesses = []
    for regime, metrics in regime_performance.items():
        if not isinstance(metrics, dict):
            continue
        sharpe = _metric_float(metrics, "sharpe_ratio", "sharpe")
        drawdown = _metric_float(metrics, "max_drawdown")
        if (sharpe is not None and sharpe < 0.0) or (drawdown is not None and drawdown < -0.2):
            weaknesses.append(regime)
    return weaknesses


def _overfitting_flags(candidate: StrategyCandidate) -> list[str]:
    flags = candidate.fitness.get("risk_flags", [])
    return [str(item) for item in flags] if isinstance(flags, list) else []


def _order_payload(order: PaperOrderRecord) -> dict[str, Any]:
    return {
        "id": str(order.id),
        "strategy_id": order.strategy_id,
        "symbol": order.symbol,
        "side": order.side,
        "quantity": float(order.quantity),
        "status": order.status,
        "created_at": order.created_at.isoformat(),
        "rejection_reason": order.rejection_reason,
    }


def _fill_payload(fill: PaperFillRecord) -> dict[str, Any]:
    return {
        "id": str(fill.id),
        "order_id": str(fill.order_id),
        "strategy_id": fill.strategy_id,
        "symbol": fill.symbol,
        "side": fill.side,
        "quantity": float(fill.quantity),
        "price": float(fill.price),
        "fees": float(fill.fees),
        "slippage_cost": float(fill.slippage_cost),
        "timestamp": fill.timestamp.isoformat(),
    }
