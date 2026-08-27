"""Explainable strategy health decisions and controlled research triggering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.campaigns.schemas import CampaignCreateRequest
from app.campaigns.service import CampaignService
from app.governance.service import DecisionService, record_to_dict
from app.models.strategy_health import (
    ResearchSchedule,
    ResearchTrigger,
    StrategyHealth,
    StrategyHealthObservation,
)
from app.strategy_health.schemas import HealthObservationRequest, HealthState, LifecycleState

RULE_VERSION = "strategy-health-v1"
MIN_OBSERVATIONS = 3
MIN_TRADES = 10


@dataclass(frozen=True)
class HealthAssessment:
    score: float
    components: dict[str, float]
    flags: list[str]
    state: HealthState
    rules: list[dict[str, Any]]


def assess_health(
    metrics: dict[str, float],
    expected: dict[str, float],
    regime_context: dict[str, Any],
    execution_context: dict[str, float],
    prior_degraded_observations: int,
) -> HealthAssessment:
    """Use transparent thresholds; do not classify tiny samples as degradation."""
    observations = int(metrics.get("observations", 0))
    trades = int(metrics.get("trades", 0))
    sufficient = observations >= MIN_OBSERVATIONS and trades >= MIN_TRADES
    expected_regime_weakness = bool(regime_context.get("expected_weakness", False))

    components = {
        "return": _ratio_component(metrics.get("rolling_return", 0.0), expected.get("return", 0.0)),
        "sharpe": _ratio_component(metrics.get("rolling_sharpe", 0.0), expected.get("sharpe", 0.0)),
        "drawdown": _drawdown_component(
            metrics.get("rolling_drawdown", 0.0), expected.get("max_drawdown", 0.0)
        ),
        "volatility": _inverse_ratio_component(
            metrics.get("rolling_volatility", 0.0), expected.get("volatility", 0.0)
        ),
        "turnover": _inverse_ratio_component(
            metrics.get("rolling_turnover", 0.0), expected.get("turnover", 0.0)
        ),
        "execution": _execution_component(execution_context),
    }
    flags: list[str] = []
    if sufficient and components["return"] < 50:
        flags.append("PERFORMANCE_DEGRADATION")
    if sufficient and components["sharpe"] < 50:
        flags.append("SHARPE_DECAY")
    if sufficient and components["drawdown"] < 40:
        flags.append("DRAWDOWN_ABNORMAL")
    if sufficient and components["turnover"] < 50:
        flags.append("TURNOVER_DRIFT")
    if components["execution"] < 50:
        flags.append("EXECUTION_DEGRADATION")
    if expected_regime_weakness:
        flags.append("REGIME_MISMATCH")

    alpha_components = [
        components[key] for key in ("return", "sharpe", "drawdown", "volatility", "turnover")
    ]
    score = round(sum(alpha_components) / len(alpha_components), 4)
    alpha_flags = [
        flag for flag in flags if flag not in {"EXECUTION_DEGRADATION", "REGIME_MISMATCH"}
    ]
    if not sufficient:
        state = HealthState.HEALTHY
    elif expected_regime_weakness and not alpha_flags:
        state = HealthState.WATCH
    elif len(alpha_flags) >= 2 and prior_degraded_observations >= 1:
        state = HealthState.DEGRADED
    elif alpha_flags or "EXECUTION_DEGRADATION" in flags:
        state = HealthState.WATCH
    else:
        state = HealthState.HEALTHY
    rules = [
        _rule(
            "MINIMUM_EVIDENCE",
            {"observations": MIN_OBSERVATIONS, "trades": MIN_TRADES},
            {"observations": observations, "trades": trades},
            sufficient,
        ),
        _rule("PERSISTENT_ALPHA_DECAY", 2, len(alpha_flags), state == HealthState.DEGRADED),
        _rule(
            "REGIME_EXPECTED_WEAKNESS",
            False,
            expected_regime_weakness,
            not expected_regime_weakness,
        ),
        _rule(
            "EXECUTION_SEPARATION", "not retirement-only", "EXECUTION_DEGRADATION" in flags, True
        ),
    ]
    return HealthAssessment(
        score=score, components=components, flags=flags, state=state, rules=rules
    )


class StrategyHealthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_observation(
        self, strategy_id: UUID, request: HealthObservationRequest
    ) -> StrategyHealth:
        prior = self._observations(strategy_id)
        prior_degraded = sum(
            1
            for item in prior[-2:]
            if len(
                set(item.flags)
                & {
                    "PERFORMANCE_DEGRADATION",
                    "SHARPE_DECAY",
                    "DRAWDOWN_ABNORMAL",
                    "TURNOVER_DRIFT",
                }
            )
            >= 2
        )
        assessment = assess_health(
            request.metrics,
            request.expected_metrics,
            request.regime_context,
            request.execution_context,
            prior_degraded,
        )
        health = self.session.get(StrategyHealth, strategy_id)
        previous_state = health.state if health else None
        lifecycle = health.lifecycle_state if health else LifecycleState.MONITORED.value
        if lifecycle == LifecycleState.RETIRE.value:
            raise ValueError("retired strategies cannot be automatically reactivated")
        if assessment.state == HealthState.DEGRADED:
            lifecycle = LifecycleState.DE_RISK.value
        elif assessment.state == HealthState.WATCH:
            lifecycle = LifecycleState.INVESTIGATE.value
        elif lifecycle in {
            LifecycleState.MONITORED.value,
            LifecycleState.INVESTIGATE.value,
            LifecycleState.DE_RISK.value,
        }:
            lifecycle = LifecycleState.RETAIN.value
        if health is None:
            health = StrategyHealth(
                strategy_id=strategy_id,
                state=assessment.state.value,
                lifecycle_state=lifecycle,
                latest_score=assessment.score,
                latest_components=assessment.components,
                active_flags=assessment.flags,
                last_evaluated_at=request.observed_at,
            )
            self.session.add(health)
        else:
            health.state = assessment.state.value
            health.lifecycle_state = lifecycle
            health.latest_score = assessment.score
            health.latest_components = assessment.components
            health.active_flags = assessment.flags
            health.last_evaluated_at = request.observed_at
        self.session.add(
            StrategyHealthObservation(
                strategy_id=strategy_id,
                observed_at=request.observed_at,
                source=request.source,
                metrics=request.metrics,
                expected_metrics=request.expected_metrics,
                components=assessment.components,
                flags=assessment.flags,
                regime_context=request.regime_context,
                execution_context=request.execution_context,
                rule_version=RULE_VERSION,
                state=assessment.state.value,
            )
        )
        self.session.flush()
        if previous_state != assessment.state.value:
            DecisionService(self.session).record(
                decision_type="STRATEGY_HEALTH_TRANSITION",
                outcome=assessment.state.value,
                actor="StrategyHealthService",
                reason="Deterministic rolling health evaluation changed the strategy state.",
                strategy_id=strategy_id,
                correlation_id=str(strategy_id),
                inputs={"metrics": request.metrics, "expected_metrics": request.expected_metrics},
                metrics={"health_score": assessment.score, "components": assessment.components},
                provenance={
                    "regime": request.regime_context,
                    "execution": request.execution_context,
                },
                versions={"strategy_health": RULE_VERSION},
                rules=assessment.rules,
            )
        if assessment.state == HealthState.DEGRADED:
            self.create_trigger(
                strategy_id,
                "STRATEGY_DEGRADED",
                {"score": assessment.score, "flags": assessment.flags},
            )
        return health

    def transition(self, strategy_id: UUID, target: HealthState, reason: str) -> StrategyHealth:
        health = self.session.get(StrategyHealth, strategy_id)
        if health is None:
            raise ValueError("strategy health not found")
        if health.state == HealthState.RETIRED.value:
            raise ValueError("retired strategies require an explicit new strategy record")
        if target == HealthState.RETIRED:
            lifecycle = LifecycleState.RETIRE.value
        elif target == HealthState.SUSPENDED:
            lifecycle = LifecycleState.DE_RISK.value
        elif target == HealthState.HEALTHY:
            lifecycle = LifecycleState.ACTIVE.value
        else:
            lifecycle = LifecycleState.INVESTIGATE.value
        health.state = target.value
        health.lifecycle_state = lifecycle
        self.session.flush()
        DecisionService(self.session).record(
            decision_type="STRATEGY_LIFECYCLE_TRANSITION",
            outcome=target.value,
            actor="StrategyHealthService",
            reason=reason,
            strategy_id=strategy_id,
            correlation_id=str(strategy_id),
            metrics={"health_score": health.latest_score, "components": health.latest_components},
            versions={"strategy_health": RULE_VERSION},
            rules=[
                _rule("EXPLICIT_LIFECYCLE_DECISION", "human_or_policy_reason", reason, bool(reason))
            ],
        )
        return health

    def create_schedule(self, payload: dict[str, Any]) -> ResearchSchedule:
        payload = {
            **payload,
            "campaign_template": CampaignCreateRequest.model_validate(
                payload["campaign_template"]
            ).model_dump(mode="json"),
        }
        schedule = ResearchSchedule(status="ACTIVE", **payload)
        self.session.add(schedule)
        self.session.flush()
        return schedule

    def run_due_schedules(self, now: datetime | None = None) -> list[ResearchTrigger]:
        now = now or datetime.now(UTC)
        triggers: list[ResearchTrigger] = []
        for schedule in self.session.scalars(
            select(ResearchSchedule).where(ResearchSchedule.status == "ACTIVE")
        ):
            last_run_at = _as_utc(schedule.last_run_at)
            periodic_due = schedule.mode in {"PERIODIC", "HYBRID"} and (
                last_run_at is None
                or now >= last_run_at + timedelta(days=schedule.cadence_days or 1)
            )
            if periodic_due:
                trigger = self.create_trigger(
                    schedule.strategy_id,
                    "PERIODIC_REVIEW",
                    {"schedule_id": str(schedule.id)},
                    schedule,
                )
                if trigger is not None:
                    triggers.append(trigger)
                    schedule.last_run_at = now
        return triggers

    def create_trigger(
        self,
        strategy_id: UUID | None,
        trigger_type: str,
        evidence: dict[str, Any],
        schedule: ResearchSchedule | None = None,
    ) -> ResearchTrigger | None:
        matching = schedule or self._event_schedule(strategy_id, trigger_type)
        if matching is None:
            return None
        key = f"{matching.id}:{trigger_type}:{datetime.now(UTC).date().isoformat()}"
        existing = self.session.scalar(
            select(ResearchTrigger).where(ResearchTrigger.deduplication_key == key)
        )
        if existing is not None:
            return None
        trigger = ResearchTrigger(
            strategy_id=strategy_id,
            trigger_type=trigger_type,
            deduplication_key=key,
            evidence=evidence,
            status="PENDING",
        )
        self.session.add(trigger)
        self.session.flush()
        campaign = CampaignService(self.session).create_campaign(
            CampaignCreateRequest.model_validate(matching.campaign_template)
        )
        trigger.campaign_id = campaign.id
        trigger.status = "CAMPAIGN_CREATED"
        DecisionService(self.session).record(
            decision_type="RESEARCH_TRIGGERED",
            outcome="CAMPAIGN_CREATED",
            actor="StrategyHealthService",
            reason=f"{trigger_type} created a controlled research campaign.",
            strategy_id=strategy_id,
            campaign_id=campaign.id,
            correlation_id=str(trigger.id),
            inputs=evidence,
            versions={"strategy_health": RULE_VERSION},
        )
        return trigger

    def timeline(self, strategy_id: UUID) -> dict[str, Any]:
        health = self.session.get(StrategyHealth, strategy_id)
        decisions = DecisionService(self.session).list_decisions(strategy_id=strategy_id)
        triggers = list(
            self.session.scalars(
                select(ResearchTrigger).where(ResearchTrigger.strategy_id == strategy_id)
            )
        )
        return {
            "health": health,
            "observations": [_observation_dict(item) for item in self._observations(strategy_id)],
            "decisions": [record_to_dict(item) for item in decisions],
            "triggers": [_trigger_dict(item) for item in triggers],
        }

    def _observations(self, strategy_id: UUID) -> list[StrategyHealthObservation]:
        return list(
            self.session.scalars(
                select(StrategyHealthObservation)
                .where(StrategyHealthObservation.strategy_id == strategy_id)
                .order_by(StrategyHealthObservation.observed_at)
            )
        )

    def _event_schedule(
        self, strategy_id: UUID | None, trigger_type: str
    ) -> ResearchSchedule | None:
        schedules = self.session.scalars(
            select(ResearchSchedule).where(
                ResearchSchedule.status == "ACTIVE",
                ResearchSchedule.mode.in_(["EVENT_TRIGGERED", "HYBRID"]),
            )
        )
        return next(
            (
                item
                for item in schedules
                if item.strategy_id == strategy_id and trigger_type in item.trigger_types
            ),
            None,
        )


def allocation_multiplier(state: str) -> float:
    return {"HEALTHY": 1.0, "WATCH": 0.9, "DEGRADED": 0.5, "SUSPENDED": 0.0, "RETIRED": 0.0}.get(
        state, 0.0
    )


def _ratio_component(value: float, expected: float) -> float:
    if expected <= 0:
        return 100.0 if value >= expected else 0.0
    return round(max(0.0, min(100.0, 100.0 * value / expected)), 4)


def _inverse_ratio_component(value: float, expected: float) -> float:
    if expected <= 0:
        return 100.0 if value <= expected else 0.0
    return round(max(0.0, min(100.0, 100.0 * expected / max(value, 1e-12))), 4)


def _drawdown_component(value: float, expected: float) -> float:
    return _inverse_ratio_component(abs(value), abs(expected))


def _execution_component(context: dict[str, float]) -> float:
    expected_cost = context.get("expected_cost_bps", 0.0)
    realized_cost = context.get("realized_cost_bps", expected_cost)
    return _inverse_ratio_component(realized_cost, expected_cost)


def _rule(rule: str, threshold: Any, observed: Any, passed: bool) -> dict[str, Any]:
    return {
        "rule": rule,
        "rule_version": RULE_VERSION,
        "threshold": threshold,
        "observed_value": observed,
        "passed": passed,
    }


def _observation_dict(item: StrategyHealthObservation) -> dict[str, Any]:
    return {
        "observed_at": item.observed_at,
        "source": item.source,
        "metrics": item.metrics,
        "components": item.components,
        "flags": item.flags,
        "state": item.state,
        "regime_context": item.regime_context,
        "execution_context": item.execution_context,
    }


def _trigger_dict(item: ResearchTrigger) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "trigger_type": item.trigger_type,
        "status": item.status,
        "campaign_id": str(item.campaign_id) if item.campaign_id else None,
        "evidence": item.evidence,
        "created_at": item.created_at,
    }


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)
