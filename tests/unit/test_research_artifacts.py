from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.data.service import DataLineageService
from app.experiments.service import ExperimentService, _bars_to_frame
from app.models.market_data import MarketBar
from app.research_artifacts.service import ResearchArtifactService, artifact_to_dict
from app.schemas.experiment import BacktestRequest


def test_experiment_artifact_captures_reproducible_snapshot(db_session: Session) -> None:
    _seed_bars(db_session, "MSFT", days=15)
    experiment = ExperimentService(db_session).run_backtest(_request())
    db_session.commit()

    artifact = ResearchArtifactService(db_session).experiment_artifact(experiment.id)
    payload = artifact_to_dict(artifact)

    assert payload["experiment_id"] == str(experiment.id)
    assert payload["dataset"]["fingerprint"]["row_count"] == 15
    assert payload["reproducibility_metadata"]["configuration"]["symbol"] == "MSFT"
    assert payload["measured_results"]["sharpe_ratio"] == experiment.metrics["sharpe_ratio"]
    assert "OOS Sharpe = 9.9" not in payload["markdown_report"]
    assert payload["charts"]["equity_curve"]
    assert payload["export_metadata"]["formats"] == ["json", "markdown"]


def test_reproduce_experiment_matches_with_same_data(db_session: Session) -> None:
    _seed_bars(db_session, "MSFT", days=15)
    experiment = ExperimentService(db_session).run_backtest(_request())
    db_session.commit()

    result = ResearchArtifactService(db_session).reproduce_experiment(experiment.id)

    assert result["match"] is True
    assert result["status"] == "matched"
    assert result["blocking_differences"] == []
    assert result["metric_comparisons"]["sharpe_ratio"]["status"] == "match"


def test_reproduce_experiment_ignores_later_mutable_market_data_change(
    db_session: Session,
) -> None:
    _seed_bars(db_session, "MSFT", days=15)
    experiment = ExperimentService(db_session).run_backtest(_request())
    changed_bar = db_session.query(MarketBar).filter_by(symbol="MSFT").first()
    assert changed_bar is not None
    changed_bar.close = Decimal("250")
    changed_bar.high = Decimal("251")
    db_session.commit()

    result = ResearchArtifactService(db_session).reproduce_experiment(experiment.id)

    assert result["match"] is True
    assert result["status"] == "matched"
    assert result["blocking_differences"] == []


def test_reproduce_experiment_detects_explicit_dataset_version_mismatch(
    db_session: Session,
) -> None:
    _seed_bars(db_session, "MSFT", days=15)
    experiment = ExperimentService(db_session).run_backtest(_request())
    changed_bar = db_session.query(MarketBar).filter_by(symbol="MSFT").first()
    assert changed_bar is not None
    changed_bar.close = Decimal("250")
    changed_bar.high = Decimal("251")
    changed_version = DataLineageService(db_session).create_dataset_version(
        name="MSFT_1d",
        bars=_bars_to_frame(list(db_session.query(MarketBar).filter_by(symbol="MSFT"))),
        provider="test_mutation",
        frequency="1d",
        parent_version_id=experiment.dataset_version_id,
        transformation="test_mutation",
    )
    db_session.commit()

    result = ResearchArtifactService(db_session).reproduce_experiment(
        experiment.id,
        dataset_version_id=changed_version.id,
    )

    assert result["match"] is False
    assert result["status"] == "mismatch"
    assert "data_mismatch" in result["blocking_differences"]
    assert "dataset_version_override" in result["blocking_differences"]


def test_markdown_report_separates_measured_result_and_interpretation(
    db_session: Session,
) -> None:
    _seed_bars(db_session, "MSFT", days=15)
    experiment = ExperimentService(db_session).run_backtest(_request())
    artifact = ResearchArtifactService(db_session).experiment_artifact(experiment.id)

    assert "## Measured Result" in artifact.markdown_report
    assert "## Interpretation" in artifact.markdown_report
    assert str(experiment.metrics["number_of_trades"]) in artifact.markdown_report


def test_reproduce_missing_experiment_raises(db_session: Session) -> None:
    service = ResearchArtifactService(db_session)

    with pytest.raises(ValueError, match="experiment not found"):
        service.reproduce_experiment(UUID("00000000-0000-0000-0000-000000000000"))


def _request() -> BacktestRequest:
    return BacktestRequest(
        symbol="MSFT",
        start=date(2024, 1, 1),
        end=date(2024, 1, 16),
        interval="1d",
        short_window=2,
        long_window=3,
        initial_capital=10_000,
        transaction_cost_bps=1,
        slippage_bps=2,
    )


def _seed_bars(session: Session, symbol: str, days: int) -> None:
    start = datetime(2024, 1, 1)
    bars = []
    for index in range(days):
        price = 100 + index + (index % 3) * 0.5
        bars.append(
            MarketBar(
                symbol=symbol,
                timestamp=start + timedelta(days=index),
                interval="1d",
                open=Decimal(str(price)),
                high=Decimal(str(price + 1)),
                low=Decimal(str(price - 1)),
                close=Decimal(str(price + 0.25)),
                volume=1_000 + index,
            )
        )
    session.add_all(bars)
    session.flush()
