"""Optimization-study coordinator layered over Mercury's campaign job queue."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaigns.optimization import ParameterSpace, candidate_rejection_reasons, parameter_hash
from app.campaigns.ranking import score_experiment
from app.campaigns.schemas import CampaignCreateRequest, OptimizationStudyCreateRequest
from app.campaigns.service import CampaignService
from app.models.campaign import OptimizationStudy, OptimizationTrial

OBJECTIVE_DEFINITION = {
    "name": "robust_validation_score",
    "components": [
        "oos_sharpe",
        "sortino",
        "drawdown",
        "turnover",
        "trade_count",
        "regime_robustness",
        "walk_forward",
        "overfitting_risk",
    ],
    "test_set_policy": "locked; finalists only after ranking",
}


class OptimizationStudyService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, request: OptimizationStudyCreateRequest) -> OptimizationStudy:
        space = ParameterSpace.from_raw(request.parameter_space)
        campaign = CampaignService(self.session).create_campaign(
            CampaignCreateRequest(
                objective=request.objective,
                symbols=request.symbols,
                start_date=request.start_date,
                end_date=request.end_date,
                interval=request.interval,
                constraints=request.constraints,
                split_definition=request.split_definition,
                parameter_space=request.parameter_space,
                optimization_method=request.search_method,
                optimization_seed=request.random_seed,
                budget={
                    "max_experiments": request.trial_budget,
                    "max_optimization_trials": request.trial_budget,
                },
            )
        )
        study = OptimizationStudy(
            campaign_id=campaign.id,
            strategy_family="moving_average_crossover",
            parameter_space=space.as_dict(),
            objective_definition=OBJECTIVE_DEFINITION,
            dataset={
                "symbols": campaign.symbols,
                "interval": campaign.interval,
                "start": campaign.start_date.isoformat(),
                "end": campaign.end_date.isoformat(),
            },
            validation_configuration=campaign.split_definition,
            trial_budget=request.trial_budget,
            search_method=request.search_method,
            random_seed=request.random_seed,
            optimizer_metadata={
                "sampler": "optuna_tpe"
                if request.search_method == "bayesian"
                else request.search_method,
                "sampler_version": "optional",
                "trial_order": "persisted",
            },
            status="CREATED",
        )
        self.session.add(study)
        self.session.flush()
        for number, planned in enumerate(
            CampaignService(self.session).list_experiments(campaign.id)
        ):
            reasons = candidate_rejection_reasons(request.parameter_space, planned.parameters)
            self.session.add(
                OptimizationTrial(
                    study_id=study.id,
                    campaign_experiment_id=planned.id,
                    trial_number=number,
                    parameters=planned.parameters,
                    parameter_hash=parameter_hash(
                        {**planned.parameters, "__symbol": planned.symbol}
                    ),
                    status="REJECTED" if reasons else "PENDING",
                    rejection_reasons=reasons,
                    objective_components={},
                    sensitivity={
                        "status": "pending",
                        "method": "neighbouring evaluated candidates",
                    },
                )
            )
        self.session.flush()
        return study

    def get(self, study_id: UUID) -> OptimizationStudy | None:
        study = self.session.get(OptimizationStudy, study_id)
        if study is not None:
            self.sync(study)
        return study

    def list_trials(self, study_id: UUID) -> list[OptimizationTrial]:
        study = self.get(study_id)
        if study is None:
            raise ValueError("optimization study not found")
        return list(
            self.session.scalars(
                select(OptimizationTrial)
                .where(OptimizationTrial.study_id == study_id)
                .order_by(OptimizationTrial.trial_number)
            )
        )

    def run(self, study_id: UUID) -> OptimizationStudy:
        study = self._require(study_id)
        CampaignService(self.session).run_campaign(study.campaign_id)
        study.status = "RUNNING"
        study.started_at = study.started_at or _utcnow()
        self.session.flush()
        return study

    def cancel(self, study_id: UUID) -> OptimizationStudy:
        study = self._require(study_id)
        CampaignService(self.session).cancel_campaign(study.campaign_id)
        study.status, study.completed_at = "CANCELLED", _utcnow()
        self.session.flush()
        return study

    def sync(self, study: OptimizationStudy) -> None:
        campaign_service = CampaignService(self.session)
        campaign = campaign_service.get_campaign(study.campaign_id)
        if campaign is None:
            return
        by_id = {item.id: item for item in campaign_service.list_experiments(campaign.id)}
        trials = list(
            self.session.scalars(
                select(OptimizationTrial).where(OptimizationTrial.study_id == study.id)
            )
        )
        for trial in trials:
            planned = by_id[trial.campaign_experiment_id]
            if planned.status == "completed":
                score, components, _ = score_experiment(planned)
                trial.status = "REJECTED" if planned.risk_flags else "VALID"
                trial.rejection_reasons = list(planned.risk_flags)
                trial.score, trial.objective_components = (
                    score,
                    _objective_components(planned, components),
                )
                trial.experiment_id = planned.experiment_id
                engine = planned.evaluation.get("validation_engine", {})
                trial.engine, trial.engine_version = engine.get("name"), engine.get("version")
                trial.completed_at = trial.completed_at or _utcnow()
            elif planned.status == "failed":
                trial.status = "FAILED"
            elif campaign.status == "cancelled":
                trial.status = "PRUNED"
                trial.rejection_reasons = ["study cancelled before execution"]
        if campaign.status == "completed":
            study.status, study.completed_at = "COMPLETED", study.completed_at or _utcnow()
        elif campaign.status == "cancelled":
            study.status, study.completed_at = "CANCELLED", study.completed_at or _utcnow()
        elif campaign.status in {"queued", "running"}:
            study.status = "RUNNING"
        self.session.flush()

    def _require(self, study_id: UUID) -> OptimizationStudy:
        study = self.get(study_id)
        if study is None:
            raise ValueError("optimization study not found")
        return study


def _objective_components(planned: Any, ranking_components: dict[str, float]) -> dict[str, Any]:
    evaluation = planned.evaluation
    robustness = evaluation.get("validation_regime_robustness", {}).get("score", 0.0)
    walk_forward = evaluation.get("walk_forward", {})
    return ranking_components | {
        "regime_robustness": robustness,
        "walk_forward_consistency": walk_forward.get("consistency", 0.0),
        "test_set_used_for_optimization": False,
        "parameter_stability": "pending neighbouring-candidate analysis",
    }


def _utcnow() -> datetime:
    return datetime.now(UTC)
