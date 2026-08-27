from dataclasses import dataclass
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.market_data.repository import MarketDataRepository
from app.memory.embedding import cosine_similarity, embed_text
from app.memory.regime import classify_asset, classify_market_regime
from app.memory.schemas import MemorySearchRequest, MemorySearchResult
from app.models.experiment import ResearchExperiment
from app.models.memory import ResearchMemoryLesson


@dataclass(frozen=True)
class RetrievedMemory:
    lesson_id: UUID
    source_experiment_id: UUID
    similarity: float
    summary: str
    tags: list[str]


class ResearchMemoryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_lesson(self, experiment: ResearchExperiment) -> ResearchMemoryLesson:
        strategy_family = str(experiment.strategy.get("strategy", "unknown"))
        bars = MarketDataRepository(self.session).list_bars(
            symbol=experiment.symbol,
            interval=experiment.interval,
            start=experiment.start_date,
            end=experiment.end_date,
        )
        market_regime = classify_market_regime(bars)
        risk_flags = list(experiment.evaluation.get("risk_findings", []))
        critique = experiment.critique
        metrics = experiment.metrics
        failure_reasons = _failure_reasons(
            metrics=metrics, risk_flags=risk_flags, critique=critique
        )
        failure_type = failure_reasons[0] if failure_reasons else None
        observations = [
            str(critique.get("lesson", "")),
            str(critique.get("suggested_next_experiment", "")),
        ]
        confidence = _lesson_confidence(metrics=metrics, failure_reasons=failure_reasons)
        lesson_text = " ".join(
            [
                experiment.objective,
                str(experiment.hypothesis.get("hypothesis", "")),
                strategy_family,
                market_regime,
                " ".join(risk_flags),
                " ".join(failure_reasons),
                " ".join(observations),
            ]
        )
        lesson = ResearchMemoryLesson(
            research_experiment_id=experiment.id,
            backtest_experiment_id=experiment.backtest_experiment_id,
            hypothesis=str(experiment.hypothesis.get("hypothesis", "")),
            strategy_family=strategy_family,
            symbol=experiment.symbol,
            asset_class=classify_asset(experiment.symbol),
            market_regime=market_regime,
            period_start=experiment.start_date.isoformat(),
            period_end=experiment.end_date.isoformat(),
            available_from=experiment.end_date,
            metrics=metrics,
            risk_flags=risk_flags,
            failure_reasons=failure_reasons,
            critic_summary=str(critique.get("lesson", "")),
            observations=[item for item in observations if item],
            confidence=confidence,
            tags=_tags(experiment.symbol, strategy_family, market_regime, failure_reasons),
            embedding=embed_text(lesson_text),
            agent_version=str(experiment.model_metadata.get("model", "unknown")),
            workflow_version=str(experiment.workflow_metadata.get("workflow_version", "unknown")),
            failure_type=failure_type,
        )
        self.session.add(lesson)
        self.session.flush()
        return lesson

    def search(self, request: MemorySearchRequest) -> list[MemorySearchResult]:
        statement = select(ResearchMemoryLesson)
        if request.symbol is not None:
            statement = statement.where(ResearchMemoryLesson.symbol == request.symbol.upper())
        if request.strategy_family is not None:
            statement = statement.where(
                ResearchMemoryLesson.strategy_family == request.strategy_family
            )
        if request.market_regime is not None:
            statement = statement.where(ResearchMemoryLesson.market_regime == request.market_regime)
        if request.failure_type is not None:
            statement = statement.where(ResearchMemoryLesson.failure_type == request.failure_type)
        if request.as_of is not None:
            statement = statement.where(ResearchMemoryLesson.available_from <= request.as_of)

        query_embedding = embed_text(request.query)
        ranked = sorted(
            (
                (lesson, cosine_similarity(query_embedding, lesson.embedding))
                for lesson in self.session.scalars(statement)
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            MemorySearchResult(
                lesson=lesson,
                similarity=round(similarity, 6),
                source_experiment_id=lesson.research_experiment_id,
            )
            for lesson, similarity in ranked[: request.top_k]
        ]

    def retrieve_for_research(
        self,
        objective: str,
        symbol: str,
        strategy_family: str | None = None,
        top_k: int = 3,
        as_of: date | None = None,
    ) -> list[RetrievedMemory]:
        search_results = self.search(
            MemorySearchRequest(
                query=f"{objective} {symbol} {strategy_family or ''}",
                symbol=symbol,
                strategy_family=strategy_family,
                top_k=top_k,
                as_of=as_of,
            )
        )
        return [
            RetrievedMemory(
                lesson_id=result.lesson.id,
                source_experiment_id=result.source_experiment_id,
                similarity=result.similarity,
                summary=result.lesson.critic_summary,
                tags=result.lesson.tags,
            )
            for result in search_results
            if result.similarity >= 0.05
        ]

    def get_for_experiment(self, experiment_id: UUID) -> list[ResearchMemoryLesson]:
        return list(
            self.session.scalars(
                select(ResearchMemoryLesson).where(
                    ResearchMemoryLesson.research_experiment_id == experiment_id
                )
            )
        )


def _failure_reasons(
    metrics: dict[str, Any], risk_flags: list[str], critique: dict[str, Any]
) -> list[str]:
    reasons: list[str] = []
    sharpe = float(metrics.get("sharpe_ratio", 0.0))
    trades = int(metrics.get("number_of_trades", 0))
    if sharpe < 1.0:
        reasons.append("low_sharpe")
    if trades < 2:
        reasons.append("low_trade_count")
    if risk_flags:
        reasons.append("risk_threshold")
    if critique.get("methodological_weaknesses"):
        reasons.append("methodology")
    return list(dict.fromkeys(reasons))


def _lesson_confidence(metrics: dict[str, Any], failure_reasons: list[str]) -> float:
    trades = int(metrics.get("number_of_trades", 0))
    base = min(0.8, 0.35 + trades * 0.05)
    if failure_reasons:
        base += 0.1
    return round(min(base, 0.9), 3)


def _tags(
    symbol: str, strategy_family: str, market_regime: str, failure_reasons: list[str]
) -> list[str]:
    return list(
        dict.fromkeys(
            [symbol.upper(), strategy_family, market_regime, *failure_reasons],
        )
    )
