from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.governance.service import DecisionService
from app.models.campaign import ResearchCampaign
from app.models.memory import ResearchMemoryLesson
from app.research_intelligence.schemas import HypothesisProposal, TriageResult


class ResearchIntelligenceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def triage(self, campaign_id: UUID, proposal: HypothesisProposal) -> TriageResult:
        campaign = self.session.get(ResearchCampaign, campaign_id)
        if campaign is None:
            raise ValueError("campaign not found")
        available = {str(x).lower() for x in campaign.datasets.get("available_data", [])}
        missing = sorted(set(x.lower() for x in proposal.required_data) - available)
        prior = [item for item in campaign.generated_hypotheses if "claim" in item]
        similar = [
            str(item["claim"])
            for item in prior
            if _similarity(proposal.claim, str(item["claim"])) >= 0.7
        ]
        memories = list(
            self.session.scalars(
                select(ResearchMemoryLesson).where(
                    ResearchMemoryLesson.strategy_family == proposal.strategy_family
                )
            )
        )
        negative = [item.critic_summary for item in memories if item.failure_reasons]
        novelty = 0.0 if similar else 1.0
        feasibility = 0.0 if missing else 1.0
        evidence = min(1.0, len(memories) / 3)
        failure_similarity = min(1.0, len(negative) / 3)
        cost = max(
            0.0,
            1.0
            - proposal.expected_research_cost
            / max(float(campaign.budget.get("max_api_cost", 1.0)), 1.0),
        )
        score = round(
            100
            * (
                0.35 * novelty
                + 0.25 * feasibility
                + 0.15 * evidence
                + 0.15 * (1 - failure_similarity)
                + 0.1 * cost
            ),
            4,
        )
        reasons = (["UNAVAILABLE_DATA"] if missing else []) + (
            ["DUPLICATE_HYPOTHESIS"] if similar else []
        )
        accepted = not reasons and score >= 55
        result = TriageResult(
            accepted=accepted,
            priority=score,
            rejection_reasons=reasons,
            similar_hypotheses=similar,
            negative_memory=negative[:3],
            score_components={
                "novelty": novelty,
                "feasibility": feasibility,
                "evidence": evidence,
                "failure_similarity": failure_similarity,
                "cost": cost,
            },
        )
        record = {**proposal.model_dump(mode="json"), **result.model_dump(mode="json")}
        if accepted:
            campaign.research_queue = sorted(
                [*campaign.research_queue, record], key=lambda x: float(x["priority"]), reverse=True
            )
        else:
            campaign.rejected_strategies = [*campaign.rejected_strategies, record]
        campaign.generated_hypotheses = [
            *campaign.generated_hypotheses,
            proposal.model_dump(mode="json"),
        ]
        DecisionService(self.session).record(
            decision_type="HYPOTHESIS_TRIAGE",
            outcome="QUEUED" if accepted else "REJECTED",
            actor="ResearchIntelligenceService",
            reason="Deterministic novelty, data, memory, and cost gate.",
            campaign_id=campaign.id,
            correlation_id=str(campaign.id),
            inputs=proposal.model_dump(mode="json"),
            metrics=result.score_components | {"priority": score},
            versions={"research_intelligence": "v1"},
            rules=[
                {"rule": "DATA_AVAILABLE", "passed": not missing, "observed_value": missing},
                {"rule": "NOT_DUPLICATE", "passed": not similar, "observed_value": similar},
            ],
        )
        self.session.flush()
        return result


def _similarity(left: str, right: str) -> float:
    a, b = set(re.findall(r"[a-z0-9]+", left.lower())), set(re.findall(r"[a-z0-9]+", right.lower()))
    return len(a & b) / len(a | b) if a | b else 0.0
