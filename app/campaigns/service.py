import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, object_session

from app.alternative_data.service import AlternativeDataService
from app.campaigns.optimization import generate_parameter_variants, idempotency_key
from app.campaigns.overfitting import detect_overfitting
from app.campaigns.portfolio import evaluate_portfolio
from app.campaigns.ranking import score_experiment
from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.splits import build_temporal_split
from app.campaigns.walk_forward import aggregate_walk_forward, build_walk_forward_windows
from app.data.service import DataLineageService
from app.evolution.schemas import EvolutionRunCreateRequest
from app.evolution.service import EvolutionService
from app.experiments.service import ExperimentService
from app.governance.service import DecisionService
from app.models.campaign import (
    CampaignExperiment,
    CampaignJob,
    PortfolioEvaluation,
    ResearchCampaign,
    StrategyRanking,
)
from app.models.data import DatasetSnapshot
from app.schemas.experiment import BacktestRequest
from app.stress_testing.service import StressTestService


class CampaignService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_campaign(self, request: CampaignCreateRequest) -> ResearchCampaign:
        split = build_temporal_split(request.start_date, request.end_date, request.split_definition)
        budget = _default_budget(request.budget)
        requirements = request.datasets.get("data_requirements", [])
        if not isinstance(requirements, list) or not all(
            isinstance(item, str) for item in requirements
        ):
            raise ValueError("datasets.data_requirements must be a list of provider names")
        AlternativeDataService(self.session).require_available_inputs(requirements)
        snapshot = self._validate_snapshot(request.dataset_snapshot_id, request.symbols)
        datasets = dict(request.datasets)
        if snapshot is not None:
            datasets = {
                **datasets,
                "dataset_snapshot_id": str(snapshot.id),
                "dataset_snapshot_fingerprint": snapshot.fingerprint,
                "dataset_snapshot_universe": snapshot.universe,
            }
        campaign = ResearchCampaign(
            objective=request.objective,
            constraints=request.constraints,
            datasets=datasets,
            dataset_snapshot_id=request.dataset_snapshot_id,
            feature_set=request.feature_set,
            symbols=[symbol.upper() for symbol in request.symbols],
            interval=request.interval,
            start_date=request.start_date,
            end_date=request.end_date,
            split_definition=split.as_dict(),
            budget={**budget, "routing_policy": request.routing_policy},
            budget_used={
                "experiments": 0,
                "llm_calls": 0,
                "runtime_seconds": 0.0,
                "api_cost": 0.0,
                "tokens": 0,
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
        DecisionService(self.session).record(
            decision_type="CAMPAIGN_PLAN",
            outcome="PLANNED",
            actor="CampaignService",
            reason="Campaign parameter variants and hypotheses were generated within budget.",
            campaign_id=campaign.id,
            correlation_id=str(campaign.id),
            inputs={
                "symbols": campaign.symbols,
                "parameter_space": request.parameter_space,
                "optimization_method": request.optimization_method,
            },
            metrics={
                "planned_experiments": len(self.list_experiments(campaign.id)),
                "optimization_trials": campaign.budget_used.get("optimization_trials", 0),
            },
            provenance={
                "split_definition": campaign.split_definition,
                "datasets": campaign.datasets,
            },
            versions={"campaign_planner": "v1"},
        )
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
                job_type="RUN_BACKTEST",
                payload={"version": 1, "campaign_experiment_id": str(planned.id)},
                idempotency_key=f"backtest:{planned.id}",
            )
            if job is not None:
                jobs.append(job)
        campaign.status = "queued" if jobs else campaign.status
        if jobs:
            DecisionService(self.session).record(
                decision_type="CAMPAIGN_QUEUE",
                outcome="QUEUED",
                actor="CampaignService",
                reason="Planned campaign experiments were queued for deterministic backtests.",
                campaign_id=campaign.id,
                correlation_id=str(campaign.id),
                inputs={"batch_size": batch_size, "job_type": "RUN_BACKTEST"},
                metrics={
                    "jobs_queued": len(jobs),
                    "planned_remaining": max(0, len(pending) - len(jobs)),
                },
                provenance={"job_ids": [str(job.id) for job in jobs]},
                versions={"campaign_state_machine": "v1"},
            )
        self.session.flush()
        return jobs

    def cancel_campaign(self, campaign_id: UUID) -> ResearchCampaign:
        campaign = self._require_campaign(campaign_id)
        previous_status = campaign.status
        campaign.status = "cancelled"
        for job in self.session.scalars(
            select(CampaignJob).where(
                CampaignJob.campaign_id == campaign.id,
                CampaignJob.status.in_(["QUEUED", "RETRYING"]),
            )
        ):
            job.status = "CANCELLED"
            job.ended_at = _utcnow()
        DecisionService(self.session).record(
            decision_type="HUMAN_OVERRIDE",
            outcome="CANCELLED",
            actor="CampaignService",
            reason="Campaign cancellation was requested through the controlled API.",
            campaign_id=campaign.id,
            correlation_id=str(campaign.id),
            inputs={"previous_status": previous_status},
            metrics={
                "queued_jobs_cancelled": sum(
                    1 for job in self.list_jobs(campaign.id) if job.status == "CANCELLED"
                )
            },
            provenance={"action": "cancel_campaign"},
            versions={"campaign_state_machine": "v1"},
        )
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

    def cancel_job(self, job_id: UUID) -> CampaignJob:
        job = self._require_job(job_id)
        if job.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            return job
        if job.status == "RUNNING":
            job.cancel_requested = True
        else:
            job.status = "CANCELLED"
            job.ended_at = _utcnow()
        self.session.flush()
        return job

    def claim_next_job(self, worker_name: str) -> CampaignJob | None:
        """Lease one eligible job with PostgreSQL SKIP LOCKED duplicate protection."""
        now = self._database_now()
        statement = (
            select(CampaignJob)
            .where(
                CampaignJob.status.in_(["QUEUED", "RETRYING"]),
                CampaignJob.available_at <= now,
                CampaignJob.cancel_requested.is_(False),
            )
            .order_by(CampaignJob.priority.desc(), CampaignJob.created_at)
            .limit(1)
        )
        if self.session.bind is not None and self.session.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        job = self.session.scalar(statement)
        if job is None:
            return None
        job.status = "RUNNING"
        job.worker = worker_name
        job.attempt_count += 1
        job.started_at = _utcnow()
        job.heartbeat_at = job.started_at
        job.error_message = None
        job.error_type = None
        self.session.flush()
        return job

    def heartbeat(self, job_id: UUID, worker_name: str) -> CampaignJob:
        job = self._require_job(job_id)
        if job.status == "RUNNING" and job.worker == worker_name:
            job.heartbeat_at = _utcnow()
            self.session.flush()
        return job

    def recover_stale_jobs(self, stale_after_seconds: int = 300) -> int:
        cutoff = self._database_now() - timedelta(seconds=stale_after_seconds)
        running_jobs = list(
            self.session.scalars(select(CampaignJob).where(CampaignJob.status == "RUNNING"))
        )
        jobs = [
            job
            for job in running_jobs
            if job.heartbeat_at is None or job.heartbeat_at.replace(tzinfo=cutoff.tzinfo) < cutoff
        ]
        for job in jobs:
            self._retry_or_fail(job, RuntimeError("worker lease expired"), force_retry=True)
        self.session.flush()
        return len(jobs)

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
        """Compatibility helper for tests and the development API.

        Production workers use claim_next_job and execute_claimed_job in separate
        transactions so the lease is committed before expensive numerical work.
        """
        job = self.claim_next_job(worker_name)
        if job is None:
            return None
        return self.execute_claimed_job(job.id, worker_name)

    def execute_claimed_job(self, job_id: UUID, worker_name: str) -> CampaignJob:
        job = self._require_job(job_id)
        if job.status != "RUNNING" or job.worker != worker_name:
            raise ValueError("job is not leased by this worker")
        started = time.perf_counter()
        try:
            self._raise_if_cancelled(job)
            if job.job_type == "RUN_BACKTEST":
                self._run_campaign_experiment(job)
            elif job.job_type == "GENERATE_REPORT":
                self.finalize_campaign(job.campaign_id)
            else:
                raise ValueError(f"unknown job type: {job.job_type}")
            self._raise_if_cancelled(job)
            job.status = "SUCCEEDED"
        except Exception as exc:
            if job.cancel_requested:
                job.status = "CANCELLED"
                job.error_message = None
            else:
                self._retry_or_fail(job, exc)
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
            for method in ["equal_weight", "inverse_volatility", "risk_parity"]:
                result = evaluate_portfolio(campaign, top, method)
                self.session.add(
                    PortfolioEvaluation(
                        campaign_id=campaign.id,
                        strategy_experiment_ids=[str(experiment.id) for experiment in top],
                        weighting_method=method,
                        weights=result.weights,
                        metrics=result.metrics,
                        diversification_benefit=float(
                            result.metrics.get("diversification_ratio", 0.0)
                        ),
                        correlation_matrix={
                            "columns": result.compatibility["columns"],
                            "matrix": result.compatibility["matrix"],
                        },
                        definition=result.definition,
                        compatibility=result.compatibility,
                        rebalance_history=result.rebalance_history,
                        incremental_benefit=result.incremental_benefit,
                        rejection_reasons=result.rejection_reasons,
                        ranking=result.ranking,
                    )
                )
        evolution_run_id = self._run_evolution_if_requested(campaign, top)
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
        campaign.final_conclusions = _build_report(
            campaign,
            completed,
            rankings,
            evolution_run_id=evolution_run_id,
        )
        campaign.status = "completed" if completed else campaign.status
        DecisionService(self.session).record(
            decision_type="CAMPAIGN_FINALIZATION",
            outcome="COMPLETED" if completed else "NO_COMPLETED_EXPERIMENTS",
            actor="CampaignService",
            reason="Campaign rankings and locked test evaluations were finalized.",
            campaign_id=campaign.id,
            correlation_id=str(campaign.id),
            inputs={"completed_experiments": [str(experiment.id) for experiment in completed]},
            metrics={
                "ranked_candidates": len(rankings),
                "top_candidate": str(rankings[0].campaign_experiment_id) if rankings else None,
                "budget_used": campaign.budget_used,
            },
            alternatives=[
                {
                    "campaign_experiment_id": str(ranking.campaign_experiment_id),
                    "rank": ranking.rank,
                    "score": ranking.score,
                    "risk_flags": ranking.risk_flags,
                }
                for ranking in sorted(rankings, key=lambda item: item.rank)[:5]
            ],
            provenance={
                "strategy_rankings": "strategy_rankings",
                "locked_test_split": campaign.split_definition.get("test"),
                "evolution_run_id": evolution_run_id,
            },
            versions={"campaign_ranker": "v1", "portfolio_evaluator": "v1"},
        )
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
            seed=request.optimization_seed,
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
        existing_job = self.session.scalar(
            select(CampaignJob).where(
                CampaignJob.campaign_id == campaign.id,
                CampaignJob.idempotency_key == idempotency_key,
            )
        )
        if existing_job is not None:
            return None
        job = CampaignJob(
            campaign_id=campaign.id,
            campaign_experiment_id=campaign_experiment.id if campaign_experiment else None,
            job_type=job_type,
            status="QUEUED",
            payload=payload,
            payload_version=int(payload.get("version", 1)),
            idempotency_key=idempotency_key,
            max_attempts=int(campaign.constraints.get("max_job_attempts", 3)),
            priority=int(campaign.constraints.get("job_priority", 0)),
            retry_history=[],
        )
        self.session.add(job)
        try:
            with self.session.begin_nested():
                self.session.flush()
        except IntegrityError:
            self.session.expunge(job)
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
        walk_forward_windows = self._run_walk_forward_evaluations(
            campaign=campaign,
            planned=planned,
            backtests=backtests,
        )
        walk_forward = aggregate_walk_forward(walk_forward_windows)
        planned.experiment_id = validation_experiment.id
        job.experiment_id = validation_experiment.id
        planned.status = "completed"
        planned.metrics = validation_experiment.metrics
        planned.evaluation = {
            "train_experiment_id": str(train_experiment.id),
            "validation_experiment_id": str(validation_experiment.id),
            "train_metrics": train_experiment.metrics,
            "validation_metrics": validation_experiment.metrics,
            "validation_regime_performance": validation_experiment.run_metadata.get(
                "regime_performance", {}
            ),
            "validation_regime_robustness": validation_experiment.run_metadata.get(
                "regime_robustness", {}
            ),
            "validation_engine": validation_experiment.run_metadata.get("backtest_engine", {}),
            "validation_return_series": validation_experiment.run_metadata.get(
                "portfolio_return_series", []
            ),
            "walk_forward_windows": walk_forward_windows,
            "walk_forward": walk_forward,
            "test_period_locked": campaign.split_definition["test"],
        }
        planned.risk_flags = flags
        if bool(campaign.constraints.get("require_stress_testing", False)):
            study = StressTestService(self.session).run(
                validation_experiment.id,
                block_size=int(campaign.constraints.get("stress_block_size", 5)),
                simulations=int(campaign.constraints.get("stress_simulations", 50)),
                seed=int(campaign.constraints.get("stress_seed", 17)),
            )
            planned.evaluation = {**planned.evaluation, "stress_test": study}
            planned.risk_flags = list(dict.fromkeys([*planned.risk_flags, *study["risk_flags"]]))
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
        DecisionService(self.session).record(
            decision_type="CAMPAIGN_EXPERIMENT_REJECTION"
            if planned.risk_flags
            else "CAMPAIGN_EXPERIMENT_ACCEPTANCE",
            outcome="REJECTED" if planned.risk_flags else "ACCEPTED",
            actor="CampaignService",
            reason="Validation backtest failed persisted risk checks."
            if planned.risk_flags
            else "Validation backtest completed without persisted risk flags.",
            campaign_id=campaign.id,
            experiment_id=validation_experiment.id,
            correlation_id=str(campaign.id),
            inputs={
                "campaign_experiment_id": str(planned.id),
                "train_experiment_id": str(train_experiment.id),
                "validation_experiment_id": str(validation_experiment.id),
                "parameters": planned.parameters,
            },
            metrics={
                "validation": validation_experiment.metrics,
                "walk_forward": walk_forward,
                "risk_flags": planned.risk_flags,
            },
            provenance={
                "split_definition": campaign.split_definition,
                "validation_engine": planned.evaluation.get("validation_engine", {}),
            },
            versions={"overfitting_detector": "v1", "campaign_state_machine": "v1"},
            rules=[
                {
                    "rule": "NO_OVERFITTING_FLAGS",
                    "rule_version": "v1",
                    "threshold": "no persisted risk flags",
                    "observed_value": planned.risk_flags,
                    "passed": not planned.risk_flags,
                }
            ],
        )

    def _run_walk_forward_evaluations(
        self,
        campaign: ResearchCampaign,
        planned: CampaignExperiment,
        backtests: ExperimentService,
    ) -> list[dict[str, Any]]:
        validation_end = date.fromisoformat(campaign.split_definition["validation"]["end"])
        min_window_days = int(planned.parameters["long_window"]) + 1
        windows = build_walk_forward_windows(
            campaign.start_date,
            validation_end,
            min_train_days=min_window_days,
            min_test_days=min_window_days,
        )
        results: list[dict[str, Any]] = []
        for window in windows:
            train_experiment = backtests.run_backtest(
                _backtest_request(
                    campaign,
                    planned,
                    window["train_start"],
                    window["train_end"],
                )
            )
            test_experiment = backtests.run_backtest(
                _backtest_request(
                    campaign,
                    planned,
                    window["test_start"],
                    window["test_end"],
                )
            )
            results.append(
                {
                    **window,
                    "train_experiment_id": str(train_experiment.id),
                    "test_experiment_id": str(test_experiment.id),
                    "train_metrics": train_experiment.metrics,
                    "test_metrics": test_experiment.metrics,
                    "uses_locked_test_split": False,
                }
            )
        return results

    def _refresh_campaign_state(self, campaign_id: UUID) -> None:
        campaign = self._require_campaign(campaign_id)
        jobs = self.list_jobs(campaign.id)
        if any(job.status in {"QUEUED", "RETRYING", "RUNNING"} for job in jobs):
            campaign.status = "running"
        elif any(job.status == "FAILED" for job in jobs):
            campaign.status = "failed"
        elif jobs:
            self.finalize_campaign(campaign.id)
        self.session.flush()

    def _require_campaign(self, campaign_id: UUID) -> ResearchCampaign:
        campaign = self.session.get(ResearchCampaign, campaign_id)
        if campaign is None:
            raise ValueError("campaign not found")
        return campaign

    def _require_job(self, job_id: UUID) -> CampaignJob:
        job = self.session.get(CampaignJob, job_id)
        if job is None:
            raise ValueError("job not found")
        return job

    def _validate_snapshot(
        self, snapshot_id: UUID | None, symbols: list[str]
    ) -> DatasetSnapshot | None:
        if snapshot_id is None:
            return None
        snapshot = self.session.get(DatasetSnapshot, snapshot_id)
        if snapshot is None:
            raise ValueError("dataset snapshot not found")
        requested = {symbol.upper() for symbol in symbols}
        missing = sorted(requested - set(snapshot.universe))
        if missing:
            raise ValueError(f"dataset snapshot is missing symbols: {missing}")
        for version_id in snapshot.dataset_version_ids:
            DataLineageService(self.session).require_version(UUID(str(version_id)))
        return snapshot

    def _database_now(self) -> datetime:
        now = _utcnow()
        if self.session.bind is not None and self.session.bind.dialect.name == "sqlite":
            return now.replace(tzinfo=None)
        return now

    def _raise_if_cancelled(self, job: CampaignJob) -> None:
        self.session.refresh(job)
        if job.cancel_requested:
            raise RuntimeError("job cancellation requested")

    def _retry_or_fail(
        self, job: CampaignJob, exc: Exception, *, force_retry: bool = False
    ) -> None:
        transient = force_retry or isinstance(
            exc, (ConnectionError, TimeoutError, OperationalError)
        )
        retryable = transient and job.attempt_count < job.max_attempts
        job.error_type = type(exc).__name__
        job.error_message = str(exc)
        history = list(job.retry_history or [])
        history.append(
            {
                "attempt": job.attempt_count,
                "at": _utcnow().isoformat(),
                "error_type": job.error_type,
                "message": job.error_message,
                "retryable": retryable,
            }
        )
        job.retry_history = history
        if retryable:
            job.status = "RETRYING"
            job.available_at = _utcnow() + timedelta(seconds=min(60, 2**job.attempt_count))
            job.worker = None
            job.heartbeat_at = None
        else:
            job.status = "FAILED"

    def _run_evolution_if_requested(
        self,
        campaign: ResearchCampaign,
        top: list[CampaignExperiment],
    ) -> str | None:
        if not campaign.constraints.get("enable_evolution"):
            return None
        if campaign.final_conclusions.get("evolution_run_id"):
            return str(campaign.final_conclusions["evolution_run_id"])
        if not top:
            return None
        seed = top[0]
        initial_population = [
            {
                "short_window": int(experiment.parameters["short_window"]),
                "long_window": int(experiment.parameters["long_window"]),
            }
            for experiment in top[:3]
        ]
        request = EvolutionRunCreateRequest(
            objective=f"Campaign evolution: {campaign.objective}",
            symbol=seed.symbol,
            start=campaign.start_date,
            end=campaign.end_date,
            interval=campaign.interval,
            initial_population=initial_population,
            generations=int(campaign.constraints.get("evolution_generations", 1)),
            population_size=max(2, len(initial_population)),
            memory_enabled=bool(campaign.constraints.get("memory_conditioned_evolution", False)),
            transaction_cost_bps=float(campaign.constraints.get("transaction_cost_bps", 1.0)),
            slippage_bps=float(campaign.constraints.get("slippage_bps", 0.0)),
        )
        run = EvolutionService(self.session).create_run(request)
        return str(run.id)


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
        dataset_version_id=_snapshot_version_id_for_symbol(campaign, planned.symbol),
        feature_version_ids=_feature_version_ids(campaign.feature_set),
    )


def _snapshot_version_id_for_symbol(campaign: ResearchCampaign, symbol: str) -> UUID | None:
    if campaign.dataset_snapshot_id is None:
        return None
    session = object_session(campaign)
    if session is None:
        raise ValueError("campaign is not attached to a database session")
    service = DataLineageService(session)
    snapshot = service.session.get(DatasetSnapshot, campaign.dataset_snapshot_id)
    if snapshot is None:
        raise ValueError("dataset snapshot not found")
    requested = symbol.upper()
    for raw_version_id in snapshot.dataset_version_ids:
        version_id = UUID(str(raw_version_id))
        version = service.require_version(version_id)
        if requested in version.symbols and version.frequency == campaign.interval:
            return version.id
    raise ValueError(f"dataset snapshot has no {campaign.interval} version for {requested}")


def _feature_version_ids(feature_set: list[dict[str, Any]]) -> list[UUID]:
    ids: list[UUID] = []
    for item in feature_set:
        raw = item.get("feature_version_id") or item.get("id")
        if raw is not None:
            ids.append(UUID(str(raw)))
    return ids


def _default_budget(raw: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "max_experiments": 12,
        "max_llm_calls": 0,
        "max_tokens": 0,
        "max_llm_cost": 0.0,
        "max_runtime_seconds": 600,
        "max_api_cost": 0.0,
        "max_optimization_trials": 12,
    }
    return {**defaults, **raw}


def _build_report(
    campaign: ResearchCampaign,
    completed: list[CampaignExperiment],
    rankings: list[StrategyRanking],
    *,
    evolution_run_id: str | None = None,
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
        "regime_performance": {
            str(experiment.id): experiment.evaluation.get("validation_metrics", {})
            | {"regime_performance": experiment.evaluation.get("validation_regime_performance", {})}
            for experiment in completed
        },
        "strategy_evolution": {
            "valid_campaign_actions": [
                "new_hypothesis_generation",
                "parameter_optimization",
                "strategy_mutation",
                "strategy_crossover",
                "portfolio_combination",
            ],
            "evolution_run_id": evolution_run_id,
            "state_machine_owner": "CampaignService",
        },
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
