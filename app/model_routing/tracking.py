from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model_routing.schemas import RoutingDecision
from app.models.model_routing import ModelUsageCall


class ModelUsageService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        decision: RoutingDecision,
        *,
        agent: str,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: float = 0.0,
        retry_count: int = 0,
        fallback_used: bool = False,
        escalation_reason: str | None = None,
        research_experiment_id: UUID | None = None,
        campaign_id: UUID | None = None,
        workflow_version_id: UUID | None = None,
    ) -> ModelUsageCall:
        model = decision.model
        cost = (input_tokens / 1000 * model.input_cost_per_1k) + (
            output_tokens / 1000 * model.output_cost_per_1k
        )
        record = ModelUsageCall(
            task_type=decision.task_type.value,
            agent=agent,
            model_id=model.model_id,
            provider=model.provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=cost,
            success=success,
            retry_count=retry_count,
            fallback_used=fallback_used,
            escalation_reason=escalation_reason,
            routing_decision={
                "policy": decision.policy.value,
                "reason": decision.reason,
                "score_components": decision.score_components,
                "downgraded_for_budget": decision.downgraded_for_budget,
            },
            research_experiment_id=research_experiment_id,
            campaign_id=campaign_id,
            workflow_version_id=workflow_version_id,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def summary(self, campaign_id: UUID | None = None) -> list[dict[str, object]]:
        stmt = select(ModelUsageCall)
        if campaign_id is not None:
            stmt = stmt.where(ModelUsageCall.campaign_id == campaign_id)
        rows: Iterable[ModelUsageCall] = self.session.scalars(stmt)
        grouped: dict[str, list[ModelUsageCall]] = {}
        for row in rows:
            grouped.setdefault(row.model_id, []).append(row)
        return [
            {
                "model": model_id,
                "provider": calls[0].provider,
                "usage": len(calls),
                "total_cost": sum(item.estimated_cost for item in calls),
                "average_latency_ms": sum(item.latency_ms for item in calls) / len(calls),
                "success_rate": sum(item.success for item in calls) / len(calls),
                "fallback_rate": sum(item.fallback_used for item in calls) / len(calls),
            }
            for model_id, calls in sorted(grouped.items())
        ]
