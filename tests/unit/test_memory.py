from sqlalchemy.orm import Session

from app.market_data.normalization import normalize_bars
from app.market_data.repository import MarketDataRepository
from app.memory.schemas import MemorySearchRequest
from app.memory.service import ResearchMemoryService
from app.research.model_client import RuleBasedResearchModelClient
from app.research.schemas import ResearchExperimentRequest
from app.research.service import ResearchExperimentService
from tests.conftest import sample_raw_bars


def _seed_bars(session: Session, symbol: str = "MSFT") -> None:
    bars = normalize_bars(sample_raw_bars(), symbol=symbol, interval="1d")
    MarketDataRepository(session).upsert_bars(bars)
    session.commit()


def _request(symbol: str = "MSFT") -> ResearchExperimentRequest:
    return ResearchExperimentRequest(
        objective=f"Explore trend-following behavior on {symbol} with deterministic data",
        symbol=symbol,
        start_date="2024-01-01",
        end_date="2024-01-11",
    )


def test_completed_research_experiment_creates_structured_memory(db_session: Session) -> None:
    _seed_bars(db_session)
    experiment = ResearchExperimentService(
        db_session, RuleBasedResearchModelClient()
    ).run_research_experiment(_request())
    db_session.commit()

    lessons = ResearchMemoryService(db_session).get_for_experiment(experiment.id)

    assert len(lessons) == 1
    lesson = lessons[0]
    assert lesson.research_experiment_id == experiment.id
    assert lesson.strategy_family == "moving_average_crossover"
    assert lesson.symbol == "MSFT"
    assert lesson.market_regime != "unknown_regime"
    assert lesson.embedding
    assert "methodology" in lesson.failure_reasons
    assert lesson.agent_version == "rule_based_research_v1"
    assert lesson.workflow_version == "research_workflow:v1"


def test_memory_search_ranks_and_filters_by_source_experiment(db_session: Session) -> None:
    _seed_bars(db_session, "MSFT")
    _seed_bars(db_session, "AAPL")
    service = ResearchExperimentService(db_session, RuleBasedResearchModelClient())
    msft_experiment = service.run_research_experiment(_request("MSFT"))
    service.run_research_experiment(_request("AAPL"))
    db_session.commit()

    results = ResearchMemoryService(db_session).search(
        MemorySearchRequest(
            query="MSFT moving average methodology risk",
            symbol="MSFT",
            strategy_family="moving_average_crossover",
            top_k=5,
        )
    )

    assert len(results) == 1
    assert results[0].source_experiment_id == msft_experiment.id
    assert results[0].similarity > 0


def test_research_workflow_retrieves_prior_memory_before_generation(db_session: Session) -> None:
    _seed_bars(db_session)
    service = ResearchExperimentService(db_session, RuleBasedResearchModelClient())
    service.run_research_experiment(_request())
    second = service.run_research_experiment(_request())
    db_session.commit()

    assert second.workflow_metadata["retrieved_memory_count"] == 1
    retrieved = second.workflow_metadata["retrieved_memory"][0]
    assert retrieved["source_experiment_id"]
    assert "moving_average_crossover" in retrieved["tags"]


def test_memory_is_unavailable_before_source_experiment_end(db_session: Session) -> None:
    _seed_bars(db_session)
    experiment = ResearchExperimentService(
        db_session, RuleBasedResearchModelClient()
    ).run_research_experiment(_request())
    db_session.commit()

    service = ResearchMemoryService(db_session)
    assert (
        service.search(
            MemorySearchRequest(query="trend methodology", symbol="MSFT", as_of="2024-01-10")
        )
        == []
    )
    assert service.search(
        MemorySearchRequest(query="trend methodology", symbol="MSFT", as_of=experiment.end_date)
    )
