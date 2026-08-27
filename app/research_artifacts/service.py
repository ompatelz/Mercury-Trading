from typing import Any
from uuid import UUID

import polars as pl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.backtesting.engine import run_moving_average_backtest
from app.data.service import DataLineageService, DataQualityError
from app.experiments.service import _bars_to_frame, _filter_frame_window, _frame_to_bars
from app.governance.service import DecisionService
from app.market_data.repository import MarketDataRepository
from app.models.agent import ResearchTraceEvent
from app.models.campaign import CampaignExperiment, ResearchCampaign, StrategyRanking
from app.models.experiment import BacktestTradeRecord, Experiment, ResearchExperiment
from app.models.market_data import MarketBar
from app.models.memory import ResearchMemoryLesson
from app.models.research_artifact import ResearchArtifact
from app.research_artifacts.fingerprints import (
    BACKTESTER_VERSION,
    STRATEGY_VERSION,
    config_fingerprint,
    current_commit,
    environment_fingerprint,
    market_data_fingerprint,
)

METRIC_TOLERANCES = {
    "sharpe_ratio": 1e-9,
    "sortino_ratio": 1e-9,
    "total_return": 1e-9,
    "annualized_return": 1e-9,
    "max_drawdown": 1e-9,
    "volatility": 1e-9,
    "ending_equity": 1e-6,
    "ending_portfolio_value": 1e-6,
}


class ResearchArtifactService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.market_data = MarketDataRepository(session)

    def get_artifact(self, artifact_id: UUID) -> ResearchArtifact | None:
        return self.session.get(ResearchArtifact, artifact_id)

    def experiment_artifact(self, experiment_id: UUID) -> ResearchArtifact:
        experiment = self._require_experiment(experiment_id)
        existing = self.session.scalar(
            select(ResearchArtifact).where(
                ResearchArtifact.artifact_type == "experiment",
                ResearchArtifact.experiment_id == experiment_id,
            )
        )
        payload = self._experiment_payload(experiment)
        if existing is None:
            artifact = ResearchArtifact(**payload)
            self.session.add(artifact)
        else:
            artifact = existing
            for key, value in payload.items():
                setattr(artifact, key, value)
        self.session.flush()
        self.session.refresh(artifact)
        return artifact

    def campaign_artifact(self, campaign_id: UUID) -> ResearchArtifact:
        campaign = self._require_campaign(campaign_id)
        existing = self.session.scalar(
            select(ResearchArtifact).where(
                ResearchArtifact.artifact_type == "campaign",
                ResearchArtifact.campaign_id == campaign_id,
            )
        )
        payload = self._campaign_payload(campaign)
        if existing is None:
            artifact = ResearchArtifact(**payload)
            self.session.add(artifact)
        else:
            artifact = existing
            for key, value in payload.items():
                setattr(artifact, key, value)
        self.session.flush()
        self.session.refresh(artifact)
        return artifact

    def reproduce_experiment(
        self, experiment_id: UUID, dataset_version_id: UUID | None = None
    ) -> dict[str, Any]:
        experiment = self._require_experiment(experiment_id)
        data_lineage = DataLineageService(self.session)
        source_dataset_version_id = dataset_version_id or experiment.dataset_version_id
        bars: list[MarketBar] = []
        frame: pl.DataFrame | None = None
        current_data_fingerprint: str | None = None
        try:
            if source_dataset_version_id is not None:
                dataset_version = data_lineage.require_version(source_dataset_version_id)
                frame = _filter_frame_window(
                    data_lineage.bars_for_version(dataset_version.id),
                    symbol=experiment.symbol,
                    start=experiment.start_date,
                    end=experiment.end_date,
                )
                bars = _frame_to_bars(frame)
                current_data_fingerprint = config_fingerprint(
                    {
                        "dataset_checksum": dataset_version.checksum,
                        "schema_version": dataset_version.schema_version,
                        "feature_versions": experiment.feature_versions,
                    }
                )
            else:
                bars = self.market_data.list_bars(
                    symbol=experiment.symbol,
                    interval=experiment.data_interval,
                    start=experiment.start_date,
                    end=experiment.end_date,
                )
                frame = _bars_to_frame(bars) if bars else None
                current_data_fingerprint = (
                    config_fingerprint(market_data_fingerprint(bars)) if bars else None
                )
        except DataQualityError as exc:
            return {
                "experiment_id": str(experiment.id),
                "status": "failed",
                "match": False,
                "blocking_differences": [str(exc)],
                "metric_comparisons": {},
            }
        if not bars or frame is None:
            return {
                "experiment_id": str(experiment.id),
                "status": "failed",
                "match": False,
                "blocking_differences": ["missing_market_data"],
                "metric_comparisons": {},
            }

        original_repro = _dict_value(experiment.run_metadata, "reproducibility")
        expected_data_fingerprint = experiment.data_fingerprint or _dict_value(
            _dict_value(original_repro, "dataset"), "fingerprint"
        )
        config = _experiment_config(experiment)
        expected_config_fingerprint = original_repro.get("configuration_fingerprint")
        current_config_fingerprint = config_fingerprint(config)
        changed_inputs = []
        if expected_data_fingerprint and expected_data_fingerprint != current_data_fingerprint:
            changed_inputs.append("data_mismatch")
        if dataset_version_id is not None and dataset_version_id != experiment.dataset_version_id:
            changed_inputs.append("dataset_version_override")
        if (
            expected_config_fingerprint
            and expected_config_fingerprint != current_config_fingerprint
        ):
            changed_inputs.append("configuration")
        if original_repro.get("commit") and original_repro.get("commit") != current_commit():
            changed_inputs.append("code_commit")
        environment = environment_fingerprint()
        original_environment = _dict_value(original_repro, "environment")
        if original_environment and original_environment.get("sha256") != environment["sha256"]:
            changed_inputs.append("environment")

        result = run_moving_average_backtest(
            bars=frame,
            short_window=int(experiment.parameters["short_window"]),
            long_window=int(experiment.parameters["long_window"]),
            initial_capital=float(experiment.parameters.get("initial_capital", 10_000.0)),
            transaction_cost_bps=experiment.transaction_cost_bps,
            slippage_bps=experiment.slippage_bps,
        )
        metric_comparisons = _compare_metrics(experiment.metrics, result.metrics)
        metric_mismatches = [
            key for key, item in metric_comparisons.items() if item["status"] == "mismatch"
        ]
        blocking = [*changed_inputs, *[f"metric:{key}" for key in metric_mismatches]]
        return {
            "experiment_id": str(experiment.id),
            "status": "matched" if not blocking else "mismatch",
            "match": not blocking,
            "blocking_differences": blocking,
            "metric_comparisons": metric_comparisons,
            "original_reproducibility": original_repro,
            "current_reproducibility": {
                "configuration": config,
                "configuration_fingerprint": current_config_fingerprint,
                "data_fingerprint": current_data_fingerprint,
                "dataset_version_id": str(source_dataset_version_id)
                if source_dataset_version_id
                else None,
                "backtester_version": BACKTESTER_VERSION,
                "strategy_version": STRATEGY_VERSION,
                "commit": current_commit(),
                "environment": environment,
            },
        }

    def _experiment_payload(self, experiment: Experiment) -> dict[str, Any]:
        campaign_experiment = self.session.scalar(
            select(CampaignExperiment).where(CampaignExperiment.experiment_id == experiment.id)
        )
        research_experiment = self.session.scalar(
            select(ResearchExperiment).where(
                ResearchExperiment.backtest_experiment_id == experiment.id
            )
        )
        memory_lessons = list(
            self.session.scalars(
                select(ResearchMemoryLesson).where(
                    ResearchMemoryLesson.backtest_experiment_id == experiment.id
                )
            )
        )
        trace_events = []
        if research_experiment is not None:
            trace_events = list(
                self.session.scalars(
                    select(ResearchTraceEvent).where(
                        ResearchTraceEvent.research_experiment_id == research_experiment.id
                    )
                )
            )
        trades = list(
            self.session.scalars(
                select(BacktestTradeRecord)
                .where(BacktestTradeRecord.experiment_id == experiment.id)
                .order_by(BacktestTradeRecord.timestamp, BacktestTradeRecord.id)
            )
        )
        repro = _dict_value(experiment.run_metadata, "reproducibility")
        risk_flags = _risk_flags(experiment, campaign_experiment)
        overfitting_flags = campaign_experiment.risk_flags if campaign_experiment else []
        measured = _measured_results(experiment.metrics)
        interpretation = _interpret_experiment(experiment.metrics, risk_flags)
        provenance = _experiment_provenance(
            experiment, research_experiment, memory_lessons, trace_events
        )
        provenance["decision_audit"] = _decision_summaries(
            self.session, experiment_id=experiment.id
        )
        payload = {
            "artifact_type": "experiment",
            "experiment_id": experiment.id,
            "campaign_id": campaign_experiment.campaign_id if campaign_experiment else None,
            "title": f"Experiment Report: {experiment.strategy_name} on {experiment.symbol}",
            "hypothesis": _hypothesis(campaign_experiment, research_experiment),
            "methodology": {
                "execution": "deterministic moving-average backtest",
                "measurement_policy": "metrics are copied from persisted experiment results",
                "missing_data_policy": "unavailable fields are reported as unavailable",
            },
            "strategy_definition": _strategy_definition(experiment, research_experiment),
            "dataset": {
                "symbol": experiment.symbol,
                "interval": experiment.data_interval,
                "start": experiment.start_date.isoformat(),
                "end": experiment.end_date.isoformat(),
                "fingerprint": repro.get("data_fingerprint", {"status": "unavailable"}),
            },
            "validation_method": _validation_method(campaign_experiment),
            "performance_metrics": experiment.metrics,
            "risk_metrics": _risk_metrics(experiment.metrics),
            "regime_metrics": _dict_value(experiment.run_metadata, "regime_performance"),
            "risk_flags": risk_flags,
            "overfitting_flags": overfitting_flags,
            "critic_summary": _critic_summary(research_experiment, memory_lessons),
            "conclusion": {
                "measured_result": measured,
                "interpretation": interpretation,
                "promotion_decision": "not_applicable",
            },
            "measured_results": measured,
            "interpretation": interpretation,
            "provenance": provenance,
            "reproducibility_metadata": repro or _legacy_reproducibility_metadata(experiment),
            "charts": _dict_value(experiment.run_metadata, "charts"),
            "export_metadata": {"formats": ["json", "markdown"], "storage": "database"},
        }
        payload["markdown_report"] = _experiment_markdown(payload, trades)
        return payload

    def _campaign_payload(self, campaign: ResearchCampaign) -> dict[str, Any]:
        completed = [
            item
            for item in self.session.scalars(
                select(CampaignExperiment)
                .where(CampaignExperiment.campaign_id == campaign.id)
                .order_by(CampaignExperiment.created_at)
            )
            if item.status == "completed"
        ]
        rankings = list(
            self.session.scalars(
                select(StrategyRanking)
                .where(StrategyRanking.campaign_id == campaign.id)
                .order_by(StrategyRanking.rank)
            )
        )
        measured = {
            "hypotheses_tested": len(completed),
            "experiment_ids": [str(item.experiment_id) for item in completed],
            "budget_used": campaign.budget_used,
            "test_results": [
                {
                    "campaign_experiment_id": str(item.id),
                    "test_experiment_id": item.evaluation.get("test_experiment_id"),
                    "metrics": item.evaluation.get("test_metrics", {}),
                }
                for item in completed
                if "test_metrics" in item.evaluation
            ],
        }
        risk_flags = sorted({flag for item in completed for flag in item.risk_flags})
        provenance = _campaign_provenance(campaign, completed)
        provenance["decision_audit"] = _decision_summaries(self.session, campaign_id=campaign.id)
        payload = {
            "artifact_type": "campaign",
            "experiment_id": None,
            "campaign_id": campaign.id,
            "title": f"Campaign Report: {campaign.objective}",
            "hypothesis": campaign.objective,
            "methodology": {
                "objective": campaign.objective,
                "constraints": campaign.constraints,
                "budget": campaign.budget,
                "stopping_reason": campaign.status,
            },
            "strategy_definition": {
                "candidate_strategies": campaign.candidate_strategies,
                "rejected_strategies": campaign.rejected_strategies,
            },
            "dataset": {
                "symbols": campaign.symbols,
                "interval": campaign.interval,
                "start": campaign.start_date.isoformat(),
                "end": campaign.end_date.isoformat(),
                "datasets": campaign.datasets,
            },
            "validation_method": {
                "split_definition": campaign.split_definition,
                "walk_forward": "stored per campaign experiment when available",
                "locked_test": campaign.split_definition.get("test"),
            },
            "performance_metrics": measured,
            "risk_metrics": {"overfitting_warnings": risk_flags},
            "regime_metrics": {
                str(item.id): item.evaluation.get("validation_regime_performance", {})
                for item in completed
            },
            "risk_flags": risk_flags,
            "overfitting_flags": risk_flags,
            "critic_summary": {"rejected_approaches": campaign.rejected_strategies},
            "conclusion": {
                "measured_result": measured,
                "interpretation": _interpret_campaign(completed, rankings, risk_flags),
                "final_conclusions": campaign.final_conclusions,
            },
            "measured_results": measured,
            "interpretation": _interpret_campaign(completed, rankings, risk_flags),
            "provenance": provenance,
            "reproducibility_metadata": {
                "campaign_id": str(campaign.id),
                "split_definition": campaign.split_definition,
                "budget": campaign.budget,
                "constraints": campaign.constraints,
                "experiment_ids": [str(item.experiment_id) for item in completed],
            },
            "charts": {
                "walk_forward_performance": [
                    {
                        "campaign_experiment_id": str(item.id),
                        **item.evaluation.get("walk_forward", {}),
                    }
                    for item in completed
                ],
                "strategy_evolution_progress": campaign.final_conclusions.get(
                    "strategy_evolution", {}
                ),
                "champion_vs_challenger": [
                    {
                        "rank": ranking.rank,
                        "score": ranking.score,
                        "campaign_experiment_id": str(ranking.campaign_experiment_id),
                    }
                    for ranking in rankings[:5]
                ],
            },
            "export_metadata": {"formats": ["json", "markdown"], "storage": "database"},
        }
        payload["markdown_report"] = _campaign_markdown(payload)
        return payload

    def _require_experiment(self, experiment_id: UUID) -> Experiment:
        experiment = self.session.get(Experiment, experiment_id)
        if experiment is None:
            raise ValueError("experiment not found")
        return experiment

    def _require_campaign(self, campaign_id: UUID) -> ResearchCampaign:
        campaign = self.session.get(ResearchCampaign, campaign_id)
        if campaign is None:
            raise ValueError("campaign not found")
        return campaign


def artifact_to_dict(artifact: ResearchArtifact) -> dict[str, Any]:
    return {
        "id": str(artifact.id),
        "artifact_type": artifact.artifact_type,
        "experiment_id": str(artifact.experiment_id) if artifact.experiment_id else None,
        "campaign_id": str(artifact.campaign_id) if artifact.campaign_id else None,
        "title": artifact.title,
        "hypothesis": artifact.hypothesis,
        "methodology": artifact.methodology,
        "strategy_definition": artifact.strategy_definition,
        "dataset": artifact.dataset,
        "validation_method": artifact.validation_method,
        "performance_metrics": artifact.performance_metrics,
        "risk_metrics": artifact.risk_metrics,
        "regime_metrics": artifact.regime_metrics,
        "risk_flags": artifact.risk_flags,
        "overfitting_flags": artifact.overfitting_flags,
        "critic_summary": artifact.critic_summary,
        "conclusion": artifact.conclusion,
        "measured_results": artifact.measured_results,
        "interpretation": artifact.interpretation,
        "provenance": artifact.provenance,
        "reproducibility_metadata": artifact.reproducibility_metadata,
        "charts": artifact.charts,
        "export_metadata": artifact.export_metadata,
        "markdown_report": artifact.markdown_report,
        "created_at": artifact.created_at.isoformat(),
        "updated_at": artifact.updated_at.isoformat(),
    }


def _experiment_config(experiment: Experiment) -> dict[str, Any]:
    return {
        "strategy_name": experiment.strategy_name,
        "symbol": experiment.symbol,
        "parameters": experiment.parameters,
        "start_date": experiment.start_date.isoformat(),
        "end_date": experiment.end_date.isoformat(),
        "data_interval": experiment.data_interval,
        "transaction_cost_bps": experiment.transaction_cost_bps,
        "slippage_bps": experiment.slippage_bps,
        "random_seed": None,
    }


def _compare_metrics(
    original: dict[str, Any], reproduced: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    comparisons = {}
    for key, original_value in original.items():
        if not isinstance(original_value, int | float):
            continue
        reproduced_value = reproduced.get(key)
        tolerance = METRIC_TOLERANCES.get(key, 1e-9)
        if not isinstance(reproduced_value, int | float):
            status = "missing"
            difference = None
        else:
            difference = float(reproduced_value) - float(original_value)
            status = "match" if abs(difference) <= tolerance else "mismatch"
        comparisons[key] = {
            "original": original_value,
            "reproduced": reproduced_value,
            "difference": difference,
            "tolerance": tolerance,
            "status": status,
        }
    return comparisons


def _risk_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = ["max_drawdown", "volatility", "sortino_ratio", "win_rate", "turnover"]
    return {key: metrics[key] for key in keys if key in metrics}


def _measured_results(metrics: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "total_return",
        "annualized_return",
        "sharpe_ratio",
        "max_drawdown",
        "number_of_trades",
        "transaction_costs",
        "slippage_costs",
        "ending_equity",
    ]
    return {key: metrics[key] for key in keys if key in metrics}


def _interpret_experiment(metrics: dict[str, Any], risk_flags: list[str]) -> dict[str, Any]:
    sharpe = metrics.get("sharpe_ratio")
    drawdown = metrics.get("max_drawdown")
    return {
        "performance": _metric_sentence("Sharpe", sharpe, positive_threshold=0.0),
        "drawdown": _drawdown_sentence(drawdown),
        "risk_flags": risk_flags,
        "trust_assessment": "review_required" if risk_flags else "no_persisted_risk_flags",
    }


def _interpret_campaign(
    completed: list[CampaignExperiment], rankings: list[StrategyRanking], risk_flags: list[str]
) -> dict[str, Any]:
    return {
        "completed_experiments": len(completed),
        "best_candidate": str(rankings[0].campaign_experiment_id) if rankings else None,
        "risk_flags": risk_flags,
        "trust_assessment": "review_required" if risk_flags else "rankings_have_no_risk_flags",
    }


def _metric_sentence(label: str, value: Any, *, positive_threshold: float) -> str:
    if not isinstance(value, int | float):
        return f"{label} is unavailable."
    direction = "positive" if float(value) > positive_threshold else "not positive"
    return f"{label} was measured as {float(value):.6g}, which is {direction}."


def _drawdown_sentence(value: Any) -> str:
    if not isinstance(value, int | float):
        return "Maximum drawdown is unavailable."
    return f"Maximum drawdown was measured as {float(value):.6g}."


def _risk_flags(
    experiment: Experiment, campaign_experiment: CampaignExperiment | None
) -> list[str]:
    flags = []
    if campaign_experiment is not None:
        flags.extend(campaign_experiment.risk_flags)
    regime_robustness = _dict_value(experiment.run_metadata, "regime_robustness")
    flags.extend(str(item) for item in regime_robustness.get("flags", []))
    return sorted(set(flags))


def _hypothesis(
    campaign_experiment: CampaignExperiment | None, research_experiment: ResearchExperiment | None
) -> str | None:
    if campaign_experiment is not None:
        value = campaign_experiment.hypothesis.get("statement")
        return str(value) if value is not None else None
    if research_experiment is not None:
        value = research_experiment.hypothesis.get("statement") or research_experiment.objective
        return str(value)
    return None


def _strategy_definition(
    experiment: Experiment, research_experiment: ResearchExperiment | None
) -> dict[str, Any]:
    if research_experiment is not None and research_experiment.strategy:
        return research_experiment.strategy
    return {
        "strategy_name": experiment.strategy_name,
        "parameters": experiment.parameters,
        "strategy_version": _dict_value(experiment.run_metadata, "reproducibility").get(
            "strategy_version", STRATEGY_VERSION
        ),
    }


def _validation_method(campaign_experiment: CampaignExperiment | None) -> dict[str, Any]:
    if campaign_experiment is None:
        return {"method": "single_backtest", "split_role": "unassigned"}
    return {
        "method": "campaign_temporal_validation",
        "split_role": campaign_experiment.split_role,
        "train_experiment_id": campaign_experiment.evaluation.get("train_experiment_id"),
        "validation_experiment_id": campaign_experiment.evaluation.get("validation_experiment_id"),
        "test_experiment_id": campaign_experiment.evaluation.get("test_experiment_id"),
        "walk_forward": campaign_experiment.evaluation.get("walk_forward", {}),
        "test_period_locked": campaign_experiment.evaluation.get("test_period_locked"),
    }


def _critic_summary(
    research_experiment: ResearchExperiment | None, memory_lessons: list[ResearchMemoryLesson]
) -> dict[str, Any]:
    return {
        "research_critique": research_experiment.critique if research_experiment else {},
        "memory_lessons": [
            {
                "id": str(item.id),
                "why_relevant": item.critic_summary,
                "observations": item.observations,
                "risk_flags": item.risk_flags,
            }
            for item in memory_lessons
        ],
    }


def _experiment_provenance(
    experiment: Experiment,
    research_experiment: ResearchExperiment | None,
    memory_lessons: list[ResearchMemoryLesson],
    trace_events: list[ResearchTraceEvent],
) -> dict[str, Any]:
    return {
        "chain": {
            "experiment": str(experiment.id),
            "backtest": str(experiment.id),
            "metrics": "experiments.metrics",
            "evaluation": "campaign_experiments.evaluation"
            if memory_lessons or research_experiment
            else None,
            "memory": [str(item.id) for item in memory_lessons],
            "report": "research_artifacts",
        },
        "research_experiment_id": str(research_experiment.id) if research_experiment else None,
        "trace_events": [
            {
                "id": item.id,
                "event_type": item.event_type,
                "event_payload": item.event_payload,
            }
            for item in sorted(trace_events, key=lambda row: row.id)
        ],
    }


def _campaign_provenance(
    campaign: ResearchCampaign, completed: list[CampaignExperiment]
) -> dict[str, Any]:
    return {
        "chain": {
            "campaign": str(campaign.id),
            "experiments": [str(item.experiment_id) for item in completed],
            "rankings": "strategy_rankings",
            "evaluation": "campaign_experiments.evaluation",
            "report": "research_artifacts",
        },
        "generated_hypotheses": campaign.generated_hypotheses,
        "rejected_approaches": campaign.rejected_strategies,
    }


def _decision_summaries(
    session: Session,
    *,
    campaign_id: UUID | None = None,
    experiment_id: UUID | None = None,
) -> list[dict[str, Any]]:
    service = DecisionService(session)
    return [
        {
            "decision_id": str(item["id"]),
            "decision_type": item["decision_type"],
            "outcome": item["outcome"],
            "reason": item["reason"],
            "content_hash": item["content_hash"],
            "integrity_verified": item["integrity"]["verified"],
            "created_at": item["created_at"].isoformat(),
        }
        for item in (
            service.explain(record.id)
            for record in service.list_decisions(
                campaign_id=campaign_id, experiment_id=experiment_id
            )
        )
        if item is not None
    ]


def _legacy_reproducibility_metadata(experiment: Experiment) -> dict[str, Any]:
    return {
        "experiment_id": str(experiment.id),
        "configuration": _experiment_config(experiment),
        "configuration_fingerprint": config_fingerprint(_experiment_config(experiment)),
        "data_fingerprint": {"status": "unavailable_for_legacy_experiment"},
        "backtester_version": BACKTESTER_VERSION,
        "strategy_version": STRATEGY_VERSION,
    }


def _experiment_markdown(payload: dict[str, Any], trades: list[BacktestTradeRecord]) -> str:
    measured = payload["measured_results"]
    interpretation = payload["interpretation"]
    return "\n".join(
        [
            f"# {payload['title']}",
            "",
            "## Experiment Summary",
            f"- Experiment ID: {payload['experiment_id']}",
            f"- Campaign ID: {payload['campaign_id'] or 'n/a'}",
            f"- Hypothesis: {payload['hypothesis'] or 'unavailable'}",
            "",
            "## Strategy",
            _json_line(payload["strategy_definition"]),
            "",
            "## Dataset & Validation",
            _json_line(payload["dataset"]),
            _json_line(payload["validation_method"]),
            "",
            "## Measured Result",
            _metric_lines(measured),
            "",
            "## Interpretation",
            _json_line(interpretation),
            "",
            "## Risk Analysis",
            _metric_lines(payload["risk_metrics"]),
            f"- Risk flags: {', '.join(payload['risk_flags']) or 'none persisted'}",
            "",
            "## Regime Performance",
            _json_line(payload["regime_metrics"] or {"status": "unavailable"}),
            "",
            "## Overfitting Checks",
            f"- Overfitting flags: {', '.join(payload['overfitting_flags']) or 'none persisted'}",
            "",
            "## Trades / Costs",
            f"- Trades persisted: {len(trades)}",
            f"- Transaction costs: {measured.get('transaction_costs', 'unavailable')}",
            f"- Slippage costs: {measured.get('slippage_costs', 'unavailable')}",
            "",
            "## Conclusion",
            _json_line(payload["conclusion"]),
            "",
            "## Decision Audit",
            _json_line(payload["provenance"].get("decision_audit", [])),
            "",
            "## Reproducibility",
            _json_line(payload["reproducibility_metadata"]),
        ]
    )


def _campaign_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# {payload['title']}",
            "",
            "## Campaign Summary",
            f"- Campaign ID: {payload['campaign_id']}",
            f"- Objective: {payload['hypothesis']}",
            "",
            "## Measured Result",
            _metric_lines(payload["measured_results"]),
            "",
            "## Interpretation",
            _json_line(payload["interpretation"]),
            "",
            "## Rejected Approaches",
            _json_line(payload["critic_summary"].get("rejected_approaches", [])),
            "",
            "## Best Candidates",
            _json_line(
                payload["conclusion"].get("final_conclusions", {}).get("best_candidates", [])
            ),
            "",
            "## Provenance",
            _json_line(payload["provenance"]),
            "",
            "## Decision Audit",
            _json_line(payload["provenance"].get("decision_audit", [])),
            "",
            "## Reproducibility",
            _json_line(payload["reproducibility_metadata"]),
        ]
    )


def _metric_lines(metrics: dict[str, Any]) -> str:
    if not metrics:
        return "- unavailable"
    return "\n".join(f"- {key}: {value}" for key, value in metrics.items())


def _json_line(payload: Any) -> str:
    return f"```json\n{payload}\n```"


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}
