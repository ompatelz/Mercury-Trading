# ruff: noqa: E501
"""Conservative, deterministic lifecycle controls for ML research candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.service import DecisionService
from app.ml_research.schemas import MLExperimentDefinition, MLObservation
from app.ml_research.service import MLResearchService
from app.models.ml import MLDriftObservation, MLModel, MLModelPromotion

RULE_VERSION = "ml-lifecycle-v1"
MIN_SAMPLES = 30
PERSISTENT_WINDOWS = 2


@dataclass(frozen=True)
class DriftAssessment:
    drift_types: list[str]
    sufficient_evidence: bool
    rules: list[dict[str, Any]]


def assess_drift(
    baseline: dict[str, Any], observed: dict[str, Any], sample_count: int
) -> DriftAssessment:
    """Assess only material, interpretable changes; small windows never trigger retraining."""
    flags: list[str] = []
    sufficient = sample_count >= MIN_SAMPLES
    if sufficient:
        if baseline.get("dataset_fingerprint") != observed.get("dataset_fingerprint"):
            flags.append("DATA_DRIFT")
        if (
            _max_difference(baseline.get("feature_means", {}), observed.get("feature_means", {}))
            > 0.5
        ):
            flags.append("FEATURE_DRIFT")
        if abs(_value(observed, "prediction_mean") - _value(baseline, "prediction_mean")) > 0.5:
            flags.append("PREDICTION_DRIFT")
        if (
            _value(observed, "ic") < _value(baseline, "ic") - 0.05
            or _value(observed, "rank_ic") < _value(baseline, "rank_ic") - 0.05
            or _value(observed, "portfolio_sharpe") < _value(baseline, "portfolio_sharpe") - 0.5
        ):
            flags.append("PERFORMANCE_DRIFT")
        if (
            _max_difference(
                baseline.get("feature_importance", {}), observed.get("feature_importance", {})
            )
            > 0.2
        ):
            flags.append("FEATURE_IMPORTANCE_DRIFT")
        if _regime_degraded(baseline.get("regime_metrics", {}), observed.get("regime_metrics", {})):
            flags.append("REGIME_PERFORMANCE_DEGRADATION")
    rules = [
        _rule("MINIMUM_SAMPLE_SIZE", MIN_SAMPLES, sample_count, sufficient),
        _rule(
            "DATASET_FINGERPRINT",
            baseline.get("dataset_fingerprint"),
            observed.get("dataset_fingerprint"),
            "DATA_DRIFT" not in flags,
        ),
        _rule(
            "FEATURE_MEAN_SHIFT",
            0.5,
            _max_difference(baseline.get("feature_means", {}), observed.get("feature_means", {})),
            "FEATURE_DRIFT" not in flags,
        ),
        _rule(
            "PREDICTION_MEAN_SHIFT",
            0.5,
            abs(_value(observed, "prediction_mean") - _value(baseline, "prediction_mean")),
            "PREDICTION_DRIFT" not in flags,
        ),
    ]
    return DriftAssessment(drift_types=flags, sufficient_evidence=sufficient, rules=rules)


class MLModelLifecycleService:
    def __init__(self, session: Session, research: MLResearchService | None = None) -> None:
        self.session = session
        self.research = research or MLResearchService()

    def record_drift(
        self,
        model_id: UUID,
        *,
        observed_at: datetime,
        window_start: datetime,
        window_end: datetime,
        sample_count: int,
        source: str,
        baseline: dict[str, Any],
        observed: dict[str, Any],
    ) -> MLDriftObservation:
        model = self._model(model_id)
        if window_start >= window_end:
            raise ValueError("drift window start must precede end")
        assessment = assess_drift(baseline, observed, sample_count)
        prior = self._drift_observations(model_id)
        current_has_drift = bool(assessment.drift_types)
        consecutive = 1 + sum(
            1 for item in reversed(prior) if current_has_drift and bool(item.drift_types)
        )
        triggered = (
            assessment.sufficient_evidence
            and consecutive >= PERSISTENT_WINDOWS
            and current_has_drift
        )
        record = MLDriftObservation(
            model_id=model.id,
            observed_at=observed_at,
            window_start=window_start,
            window_end=window_end,
            sample_count=sample_count,
            source=source,
            baseline=baseline,
            observed=observed,
            drift_types=assessment.drift_types,
            consecutive_windows=consecutive if current_has_drift else 0,
            retraining_triggered=triggered,
            rule_version=RULE_VERSION,
        )
        self.session.add(record)
        self.session.flush()
        DecisionService(self.session).record(
            decision_type="MODEL_DRIFT_ASSESSED",
            outcome="RETRAINING_TRIGGERED" if triggered else "MONITORED",
            actor="MLModelLifecycleService",
            reason="Persistent, adequately sampled drift is required before retraining is eligible.",
            correlation_id=str(model.id),
            inputs={"model_id": str(model.id), "source": source, "sample_count": sample_count},
            metrics={
                "drift_types": assessment.drift_types,
                "consecutive_windows": record.consecutive_windows,
            },
            versions={"ml_lifecycle": RULE_VERSION},
            rules=[
                *assessment.rules,
                _rule(
                    "PERSISTENT_DRIFT", PERSISTENT_WINDOWS, record.consecutive_windows, triggered
                ),
            ],
        )
        return record

    def retrain(
        self,
        parent_model_id: UUID,
        definition: MLExperimentDefinition,
        rows: list[MLObservation],
        trigger: str,
    ) -> MLModel:
        parent = self._model(parent_model_id)
        if trigger not in {
            "SCHEDULED",
            "PERSISTENT_DRIFT",
            "NEW_DATASET",
            "PERFORMANCE_DEGRADATION",
        }:
            raise ValueError("unsupported retraining trigger")
        if definition.experiment_key == parent.model_key:
            raise ValueError("retrained candidate requires a new experiment_key")
        if trigger == "PERSISTENT_DRIFT" and not any(
            item.retraining_triggered for item in self._drift_observations(parent.id)
        ):
            raise ValueError(
                "persistent drift retraining requires a recorded persistent drift trigger"
            )
        if (
            trigger == "NEW_DATASET"
            and definition.dataset_fingerprint == parent.dataset_fingerprint
        ):
            raise ValueError("new dataset retraining requires a changed dataset fingerprint")
        if trigger == "PERFORMANCE_DEGRADATION" and not any(
            "PERFORMANCE_DRIFT" in item.drift_types for item in self._drift_observations(parent.id)
        ):
            raise ValueError(
                "performance retraining requires a recorded performance drift observation"
            )
        result = self.research.run(definition, rows)
        candidate = self.research.persist(
            self.session,
            definition,
            result,
            parent_model_id=parent.id,
            lifecycle_metadata={
                "deployment_state": "RESEARCH_ONLY",
                "retraining_trigger": trigger,
                "parent_model_key": parent.model_key,
            },
        )
        DecisionService(self.session).record(
            decision_type="MODEL_RETRAINED",
            outcome="CANDIDATE_CREATED",
            actor="MLModelLifecycleService",
            reason="Retraining creates a research candidate; it cannot promote or deploy itself.",
            correlation_id=str(candidate.id),
            inputs={"parent_model_id": str(parent.id), "trigger": trigger},
            metrics=result["test"],
            versions={"ml_lifecycle": RULE_VERSION, "model_version": definition.model_version},
            rules=[
                _rule(
                    "NO_AUTOMATIC_PROMOTION",
                    False,
                    candidate.status == "CHAMPION",
                    candidate.status != "CHAMPION",
                )
            ],
        )
        return candidate

    def decide_promotion(
        self, champion_model_id: UUID | None, candidate_model_id: UUID, evidence: dict[str, Any]
    ) -> MLModelPromotion:
        candidate = self._model(candidate_model_id)
        champion = self._model(champion_model_id) if champion_model_id else None
        if champion is not None and champion.id == candidate.id:
            raise ValueError("candidate and champion must be different models")
        candidate_metrics = evidence["candidate_oos"]
        champion_metrics = evidence.get("champion_oos", {})
        enough = int(candidate_metrics["sample_count"]) >= MIN_SAMPLES
        beats_ic = (
            champion is None
            or float(candidate_metrics["ic"]) >= float(champion_metrics["ic"]) + 0.01
        )
        beats_rank = champion is None or float(candidate_metrics["rank_ic"]) >= float(
            champion_metrics["rank_ic"]
        )
        beats_sharpe = champion is None or float(candidate_metrics["sharpe"]) >= float(
            champion_metrics["sharpe"]
        )
        protects_drawdown = champion is None or float(candidate_metrics["max_drawdown"]) >= float(
            champion_metrics["max_drawdown"]
        )
        eligible = candidate.status == "VALIDATED"
        stress_passed = bool(evidence["stress_passed"])
        regime_passed = bool(evidence["regime_passed"])
        promoted = all(
            (
                enough,
                beats_ic,
                beats_rank,
                beats_sharpe,
                protects_drawdown,
                eligible,
                stress_passed,
                regime_passed,
            )
        )
        reason = (
            "Challenger met every locked OOS, stress, and regime criterion."
            if promoted
            else "Challenger did not meet the locked ML promotion criteria."
        )
        promotion = MLModelPromotion(
            candidate_model_id=candidate.id,
            champion_model_id=champion.id if champion else None,
            decision="PROMOTE" if promoted else "REJECT",
            reason=reason,
            evidence=evidence,
        )
        self.session.add(promotion)
        if promoted:
            if champion is not None:
                champion.status = "SUPERSEDED"
            candidate.status = "CHAMPION"
        self.session.flush()
        rules = [
            _rule(
                "CANDIDATE_VALIDATED",
                "VALIDATED",
                candidate.status if not promoted else "VALIDATED",
                eligible,
            ),
            _rule("MINIMUM_OOS_SAMPLES", MIN_SAMPLES, candidate_metrics["sample_count"], enough),
            _rule("OOS_IC_IMPROVEMENT", 0.01, candidate_metrics["ic"], beats_ic),
            _rule(
                "OOS_RANK_IC_NON_REGRESSION",
                champion_metrics.get("rank_ic"),
                candidate_metrics["rank_ic"],
                beats_rank,
            ),
            _rule(
                "OOS_SHARPE_NON_REGRESSION",
                champion_metrics.get("sharpe"),
                candidate_metrics["sharpe"],
                beats_sharpe,
            ),
            _rule(
                "DRAWDOWN_NON_REGRESSION",
                champion_metrics.get("max_drawdown"),
                candidate_metrics["max_drawdown"],
                protects_drawdown,
            ),
            _rule("STRESS_EVALUATION", True, stress_passed, stress_passed),
            _rule("REGIME_EVALUATION", True, regime_passed, regime_passed),
        ]
        DecisionService(self.session).record(
            decision_type="ML_MODEL_PROMOTION" if promoted else "ML_MODEL_REJECTION",
            outcome=promotion.decision,
            actor="MLModelLifecycleService",
            reason=reason,
            correlation_id=str(candidate.id),
            inputs={
                "candidate_model_id": str(candidate.id),
                "champion_model_id": str(champion.id) if champion else None,
            },
            metrics=candidate_metrics,
            alternatives=[champion_metrics] if champion else [],
            provenance={
                "stress": evidence.get("stress_summary", {}),
                "regime": evidence.get("regime_summary", {}),
            },
            versions={"ml_lifecycle": RULE_VERSION},
            rules=rules,
        )
        return promotion

    def lineage(self, model_id: UUID) -> dict[str, Any]:
        model = self._model(model_id)
        ancestors: list[dict[str, Any]] = []
        current: MLModel | None = model
        while current is not None:
            ancestors.append(_model_summary(current))
            current = (
                self.session.get(MLModel, current.parent_model_id)
                if current.parent_model_id
                else None
            )
        return {
            "model": _model_summary(model),
            "ancestors": ancestors,
            "drift_observations": [
                _drift_summary(item) for item in self._drift_observations(model.id)
            ],
            "promotion_decisions": [
                _promotion_summary(item)
                for item in self.session.scalars(
                    select(MLModelPromotion)
                    .where(MLModelPromotion.candidate_model_id == model.id)
                    .order_by(MLModelPromotion.created_at)
                )
            ],
        }

    def _model(self, model_id: UUID | None) -> MLModel:
        model = self.session.get(MLModel, model_id)
        if model is None:
            raise ValueError("ML model not found")
        return model

    def _drift_observations(self, model_id: UUID) -> list[MLDriftObservation]:
        return list(
            self.session.scalars(
                select(MLDriftObservation)
                .where(MLDriftObservation.model_id == model_id)
                .order_by(MLDriftObservation.observed_at)
            )
        )


def _value(values: dict[str, Any], key: str) -> float:
    return float(values.get(key, 0.0))


def _max_difference(left: dict[str, Any], right: dict[str, Any]) -> float:
    keys = set(left) | set(right)
    return max(
        (abs(float(left.get(key, 0.0)) - float(right.get(key, 0.0))) for key in keys), default=0.0
    )


def _regime_degraded(baseline: dict[str, Any], observed: dict[str, Any]) -> bool:
    return any(
        float(observed.get(key, {}).get("ic", 0.0)) < float(value.get("ic", 0.0)) - 0.05
        for key, value in baseline.items()
    )


def _rule(rule: str, threshold: Any, observed: Any, passed: bool) -> dict[str, Any]:
    return {
        "rule": rule,
        "rule_version": RULE_VERSION,
        "threshold": threshold,
        "observed_value": observed,
        "passed": passed,
    }


def _model_summary(model: MLModel) -> dict[str, Any]:
    return {
        "id": str(model.id),
        "model_key": model.model_key,
        "status": model.status,
        "dataset_fingerprint": model.dataset_fingerprint,
        "parent_model_id": str(model.parent_model_id) if model.parent_model_id else None,
        "lifecycle_metadata": model.lifecycle_metadata,
    }


def _drift_summary(item: MLDriftObservation) -> dict[str, Any]:
    return {
        "observed_at": item.observed_at,
        "sample_count": item.sample_count,
        "drift_types": item.drift_types,
        "consecutive_windows": item.consecutive_windows,
        "retraining_triggered": item.retraining_triggered,
    }


def _promotion_summary(item: MLModelPromotion) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "decision": item.decision,
        "reason": item.reason,
        "created_at": item.created_at,
    }
