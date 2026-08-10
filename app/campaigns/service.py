import time
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.campaigns.optimization import generate_parameter_variants, idempotency_key
from app.campaigns.overfitting import detect_overfitting
from app.campaigns.portfolio import evaluate_portfolio
from app.campaigns.ranking import score_experiment
from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.splits import build_temporal_split
from app.campaigns.walk_forward import aggregate_walk_forward, build_walk_forward_windows
from app.experiments.service import ExperimentService
from app.models.campaign import (
    CampaignExperiment,
    CampaignJob,
    PortfolioEvaluation,
    ResearchCampaign,
    StrategyRanking,
)
from app.schemas.experiment import BacktestRequest


class CampaignService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_campaign(self, request: CampaignCreateRequest) -> ResearchCampaign:
        split = build_temporal_split(request.start_date, request.end_date, request.split_definition)
        budget = _default_budget(request.budget)
        campaign = ResearchCampaign(
            objective=request.objective,
            constraints=request.constraints,
            datasets=request.datasets,
            symbols=[symbol.upper() for symbol in request.symbols],
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            split_definition=split.as_dict(),
            budget=budget,
            budget_used={
                "experiments": 0,
                "llm_calls": 0,
                "runtime_seconds": 0.0,
                "api_cost": 0.0,
                "optimization_trials": 0,
                "test_evaluations": 0,
            },
            status="created",
            generated_hypotheses=[],
            candidate_strategies=[],
            rejected_strategies=[],
            final_conclusions={},
            stop_conditions=request.stop_conditions,
        )
        self.session.add(campaign)
        self.session.flush()
        self._plan_campaign(campaign, request)
        self.session.flush()
        self.session.refresh(campaign)
        return campaign

    def list_campaigns(self) -> list[ResearchCampaign]:
        return list(
            self.session.scalars(
                select(ResearchCampaign).order_by(ResearchCampaign.created_at.desc())
            )
        )

    def get_campaign(self, campaign_id: UUID) -> ResearchCampaign | None:
        return self.session.get(ResearchCampaign, campaign_id)

    def run_campaign(self, campaign_id: UUID, batch_size: int | None = None) -> list[CampaignJob]:
        campaign = self._require_campaign(campaign_id)
        if campaign.status == "cancelled":
            raise ValueError("cancelled campaigns cannot be run")
        pending = list(
            self.session.scalars(
                select(CampaignExperiment)
                .where(
                    CampaignExperiment.campaign_id == campaign.id,
                    CampaignExperiment.status == "planned",
                )
                .order_by(CampaignExperiment.created_at)
            )
        )
        if batch_size is not None:
            pending = pending[:batch_size]
        jobs: list[CampaignJob] = []
        for planned in pending:
            job = self._create_job(
                campaign=campaign,
                campaign_experiment=planned,
                job_type="backtest_experiment",
                payload={"campaign_experiment_id": str(planned.id)},
                idempotency_key=f"backtest:{planned.id}",
            )
            if job is not None:
                jobs.append(job)
        campaign.status = "queued" if jobs else campaign.status
        self.session.flush()
        return jobs

    def cancel_campaign(self, campaign_id: UUID) -> ResearchCampaign:
        campaign = self._require_campaign(campaign_id)
        campaign.status = "cancelled"
        for job in self.session.scalars(
            select(CampaignJob).where(
                CampaignJob.campaign_id == campaign.id,
                CampaignJob.status.in_(["queued", "retrying"]),
            )
        ):
            job.status = "cancelled"
            job.ended_at = _utcnow()
        self.session.flush()
        self.session.refresh(campaign)
        return campaign

    def list_jobs(self, campaign_id: UUID | None = None) -> list[CampaignJob]:
        statement = select(CampaignJob).order_by(CampaignJob.created_at)
        if campaign_id is not None:
            statement = statement.where(CampaignJob.campaign_id == campaign_id)
        return list(self.session.scalars(statement))

    def get_job(self, job_id: UUID) -> CampaignJob | None:
        return self.session.get(CampaignJob, job_id)

    def list_experiments(self, campaign_id: UUID) -> list[CampaignExperiment]:
        return list(
            self.session.scalars(
                select(CampaignExperiment)
                .where(CampaignExperiment.campaign_id == campaign_id)
                .order_by(CampaignExperiment.created_at)
            )
        )

    def list_rankings(self, campaign_id: UUID) -> list[StrategyRanking]:
        return list(
            self.session.scalars(
                select(StrategyRanking)
                .where(StrategyRanking.campaign_id == campaign_id)
                .order_by(StrategyRanking.rank)
            )
        )

    def list_portfolios(self, campaign_id: UUID) -> list[PortfolioEvaluation]:
        return list(
            self.session.scalars(
                select(PortfolioEvaluation)
                .where(PortfolioEvaluation.campaign_id == campaign_id)
                .order_by(PortfolioEvaluation.created_at.desc())
            )
        )

    def get_report(self, campaign_id: UUID) -> dict[str, Any]:
        campaign = self._require_campaign(campaign_id)
        if not campaign.final_conclusions:
            self.finalize_campaign(campaign_id)
            self.session.refresh(campaign)
        return campaign.final_conclusions

    def process_next_job(self, worker_name: str) -> CampaignJob | None:
        job = self.session.scalar(
            select(CampaignJob)
            .where(CampaignJob.status.in_(["queued", "retrying"]))
            .order_by(CampaignJob.created_at)
        )
        if job is None:
            return None
        started = time.perf_counter()
        job.status = "running"
        job.worker = worker_name
        job.attempt_count += 1
        job.started_at = _utcnow()
        job.error_message = None
        self.session.flush()
        try:
            if job.job_type == "backtest_experiment":
                self._run_campaign_experiment(job)
            elif job.job_type == "generate_report":
                self.finalize_campaign(job.campaign_id)
            else:
                raise ValueError(f"unknown job type: {job.job_type}")
            job.status = "succeeded"
        except Exception as exc:
            job.error_message = str(exc)
            job.status = "retrying" if job.attempt_count < job.max_attempts else "failed"
            raise
        finally:
            job.ended_at = _utcnow()
            job.runtime_ms = round((time.perf_counter() - started) * 1000.0, 6)
            campaign = self._require_campaign(job.campaign_id)
            campaign.budget_used = {
                **campaign.budget_used,
                "runtime_seconds": round(
                    float(campaign.budget_used.get("runtime_seconds", 0.0))
                    + (job.runtime_ms or 0.0) / 1000.0,
                    6,
                ),
            }
            self.session.flush()
        self._refresh_campaign_state(job.campaign_id)
        self.session.refresh(job)
        return job

    def finalize_campaign(self, campaign_id: UUID) -> ResearchCampaign:
        campaign = self._require_campaign(campaign_id)
        completed = [
            experiment
            for experiment in self.list_experiments(campaign.id)
            if experiment.status == "completed"
        ]
        self.session.execute(
            delete(StrategyRanking).where(StrategyRanking.campaign_id == campaign.id)
        )
        ranked_rows = sorted((score_experiment(experiment), experiment) for experiment in completed)
        ranked_rows.reverse()
        rankings: list[StrategyRanking] = []
        for index, ((score, components, reason), experiment) in enumerate(ranked_rows, start=1):
            rankings.append(
                StrategyRanking(
                    campaign_id=campaign.id,
                    campaign_experiment_id=experiment.id,
                    rank=index,
                    score=score,
                    component_scores=components,
                    ranking_reason=reason,
                    risk_flags=experiment.risk_flags,
                )
            )
        self.session.add_all(rankings)
        top = [experiment for _, experiment in ranked_rows[:3]]
        self._run_locked_test_evaluations(campaign, top)
        self.session.execute(
            delete(PortfolioEvaluation).where(PortfolioEvaluation.campaign_id == campaign.id)
        )
        if top:
            for method in ["equal_weight", "volatility_adjusted", "risk_parity"]:
                weights, metrics, benefit, correlations = evaluate_portfolio(top, method)
                self.session.add(
                    PortfolioEvaluation(
                        campaign_id=campaign.id,
                        strategy_experiment_ids=[str(experiment.id) for experiment in top],
                        weighting_method=method,
                        weights=weights,
                        metrics=metrics,
                        diversification_benefit=benefit,
                        correlation_matrix=correlations,
                    )
                )
        campaign.candidate_strategies = [
            {
                "campaign_experiment_id": str(experiment.id),
                "score": score_tuple[0],
                "parameters": experiment.parameters,
                "symbol": experiment.symbol,
            }
            for score_tuple, experiment in ranked_rows
            if not experiment.risk_flags
        ][:5]
        campaign.rejected_strategies = [
            {
                "campaign_experiment_id": str(experiment.id),
                "risk_flags": experiment.risk_flags,
                "parameters": experiment.parameters,
                "symbol": experiment.symbol,
            }
            for _, experiment in ranked_rows
            if experiment.risk_flags
        ]
        campaign.final_conclusions = _build_report(campaign, completed, rankings)
        campaign.status = "completed" if completed else campaign.status
        self.session.flush()
        self.session.refresh(campaign)
        return campaign

    def _run_locked_test_evaluations(
        self, campaign: ResearchCampaign, experiments: list[CampaignExperiment]
    ) -> None:
        test_period = campaign.split_definition["test"]
        backtests = ExperimentService(self.session)
        test_evaluations = 0
        for experiment in experiments:
            if "test_metrics" in experiment.evaluation:
                continue
            test_experiment = backtests.run_backtest(
                _backtest_request(
                    campaign,
                    experiment,
                    test_period["start"],
                    test_period["end"],
                )
            )
            experiment.evaluation = {
                **experiment.evaluation,
                "test_experiment_id": str(test_experiment.id),
                "test_metrics": test_experiment.metrics,
                "test_evaluated_once": True,
            }
            test_evaluations += 1
        campaign.budget_used = {
            **campaign.budget_used,
            "test_evaluations": int(campaign.budget_used.get("test_evaluations", 0))
            + test_evaluations,
        }

    def _plan_campaign(self, campaign: ResearchCampaign, request: CampaignCreateRequest) -> None:
        max_experiments = int(campaign.budget.get("max_experiments", 12))
        max_trials = min(
            int(campaign.budget.get("max_optimization_trials", max_experiments)),
            max_experiments,
        )
        variants = generate_parameter_variants(
            parameter_space=request.parameter_space,
            method=request.optimization_method,
            max_variants=max_trials,
        )
        planned: list[CampaignExperiment] = []
        hypotheses: list[dict[str, Any]] = []
        for symbol in campaign.symbols:
            for parameters in variants:
                if len(planned) >= max_experiments:
                    break
                hypothesis = {
                    "research_question": campaign.objective,
                    "statement": (
                        f"{symbol} medium-term momentum may produce robust validation "
                        "returns after costs."
                    ),
                    "optimization_method": request.optimization_method,
                }
                key = idempotency_key(str(campaign.id), symbol, parameters)
                hypotheses.append(hypothesis)
                planned.append(
                    CampaignExperiment(
                        campaign_id=campaign.id,
                        idempotency_key=key,
                        hypothesis=hypothesis,
                        strategy_family="moving_average_crossover",
                        parameters=parameters,
                        symbol=symbol,
                        split_role="validation",
                        status="planned",
                        metrics={},
                        evaluation={},
                        risk_flags=[],
                    )
                )
            if len(planned) >= max_experiments:
                break
        campaign.generated_hypotheses = hypotheses
        campaign.budget_used = {
            **campaign.budget_used,
            "optimization_trials": len(planned),
        }
        self.session.add_all(planned)

    def _create_job(
        self,
        campaign: ResearchCampaign,
        campaign_experiment: CampaignExperiment | None,
        job_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> CampaignJob | None:
        job = CampaignJob(
            campaign_id=campaign.id,
            campaign_experiment_id=campaign_experiment.id if campaign_experiment else None,
            job_type=job_type,
            status="queued",
            payload=payload,
            idempotency_key=idempotency_key,
            max_attempts=int(campaign.constraints.get("max_job_attempts", 3)),
        )
        self.session.add(job)
        try:
            self.session.flush()
        except IntegrityError:
            self.session.rollback()
            return None
        return job

    def _run_campaign_experiment(self, job: CampaignJob) -> None:
        campaign = self._require_campaign(job.campaign_id)
        campaign_experiment_id = job.campaign_experiment_id
        if campaign_experiment_id is None:
            raise ValueError("backtest job is missing campaign_experiment_id")
        planned = self.session.get(CampaignExperiment, campaign_experiment_id)
        if planned is None:
            raise ValueError("campaign experiment not found")
        if planned.status == "completed":
            return
        split = campaign.split_definition
        train = split["train"]
        validation = split["validation"]
        backtests = ExperimentService(self.session)
        train_experiment = backtests.run_backtest(
            _backtest_request(campaign, planned, train["start"], train["end"])
        )
        validation_experiment = backtests.run_backtest(
            _backtest_request(campaign, planned, validation["start"], validation["end"])
        )
        flags = detect_overfitting(
            train_metrics=train_experiment.metrics,
            validation_metrics=validation_experiment.metrics,
            constraints=campaign.constraints,
        )
        walk_forward = aggregate_walk_forward(
            [
                validation_experiment.metrics
                for _ in build_walk_forward_windows(campaign.start_date, campaign.end_date)
            ]
        )
        planned.experiment_id = validation_experiment.id
        planned.status = "completed"
        planned.metrics = validation_experiment.metrics
        planned.evaluation = {
            "train_experiment_id": str(train_experiment.id),
            "validation_experiment_id": str(validation_experiment.id),
            "train_metrics": train_experiment.metrics,
            "validation_metrics": validation_experiment.metrics,
            "walk_forward": walk_forward,
            "test_period_locked": campaign.split_definition["test"],
        }
        planned.risk_flags = flags
        campaign.budget_used = {
            **campaign.budget_used,
            "experiments": int(campaign.budget_used.get("experiments", 0)) + 1,
        }
        if planned.risk_flags:
            campaign.rejected_strategies = [
                *campaign.rejected_strategies,
                {
                    "campaign_experiment_id": str(planned.id),
                    "risk_flags": planned.risk_flags,
                    "parameters": planned.parameters,
                },
            ]

    def _refresh_campaign_state(self, campaign_id: UUID) -> None:
        campaign = self._require_campaign(campaign_id)
        jobs = self.list_jobs(campaign.id)
        if any(job.status in {"queued", "retrying", "running"} for job in jobs):
            campaign.status = "running"
        elif any(job.status == "failed" for job in jobs):
            campaign.status = "failed"
        elif jobs:
            self.finalize_campaign(campaign.id)
        self.session.flush()

    def _require_campaign(self, campaign_id: UUID) -> ResearchCampaign:
        campaign = self.session.get(ResearchCampaign, campaign_id)
        if campaign is None:
            raise ValueError("campaign not found")
        return campaign


def _backtest_request(
    campaign: ResearchCampaign,
    planned: CampaignExperiment,
    start_date: str,
    end_date: str,
) -> BacktestRequest:
    return BacktestRequest(
        symbol=planned.symbol,
        start=date.fromisoformat(start_date),
        end=date.fromisoformat(end_date),
        interval=campaign.interval,
        short_window=int(planned.parameters["short_window"]),
        long_window=int(planned.parameters["long_window"]),
        initial_capital=float(campaign.constraints.get("initial_capital", 10_000.0)),
        transaction_cost_bps=float(campaign.constraints.get("transaction_cost_bps", 1.0)),
        slippage_bps=float(campaign.constraints.get("slippage_bps", 0.0)),
    )


def _default_budget(raw: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "max_experiments": 12,
        "max_llm_calls": 0,
        "max_runtime_seconds": 600,
        "max_api_cost": 0.0,
        "max_optimization_trials": 12,
    }
    return {**defaults, **raw}


def _build_report(
    campaign: ResearchCampaign,
    completed: list[CampaignExperiment],
    rankings: list[StrategyRanking],
) -> dict[str, Any]:
    return {
        "research_question": campaign.objective,
        "hypotheses_tested": len(completed),
        "experiment_ids": [str(experiment.experiment_id) for experiment in completed],
        "rejected_approaches": campaign.rejected_strategies,
        "best_candidates": [
            {
                "campaign_experiment_id": str(ranking.campaign_experiment_id),
                "rank": ranking.rank,
                "score": ranking.score,
                "risk_flags": ranking.risk_flags,
            }
            for ranking in sorted(rankings, key=lambda item: item.rank)[:5]
        ],
        "walk_forward_results": [
            experiment.evaluation.get("walk_forward", {}) for experiment in completed
        ],
        "test_results": [
            {
                "campaign_experiment_id": str(experiment.id),
                "test_experiment_id": experiment.evaluation.get("test_experiment_id"),
                "metrics": experiment.evaluation.get("test_metrics", {}),
            }
            for experiment in completed
            if "test_metrics" in experiment.evaluation
        ],
        "overfitting_warnings": sorted(
            {flag for experiment in completed for flag in experiment.risk_flags}
        ),
        "portfolio_combinations": "available through /campaigns/{id}/portfolios",
        "relevant_previous_memory": "research memory remains available to campaign planners",
        "conclusion": (
            "Campaign completed with explainable rankings. Final candidates were evaluated "
            "on the locked test split after parameter exploration."
        ),
        "recommended_next_research": "Promote only high-scoring candidates with low risk flags.",
        "budget_used": campaign.budget_used,
        "split_definition": campaign.split_definition,
    }


def _utcnow() -> datetime:
    return datetime.now(UTC)
