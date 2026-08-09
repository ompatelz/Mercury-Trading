from typing import Protocol, SupportsFloat, SupportsInt, cast

from app.research.schemas import (
    CriticOutput,
    EvaluationOutput,
    HypothesisOutput,
    StrategySpecification,
)


class ResearchModelClient(Protocol):
    provider: str
    model: str
    temperature: float | None

    def generate_hypothesis(self, objective: str, symbol: str) -> HypothesisOutput:
        """Return a structured, testable hypothesis."""

    def specify_strategy(self, hypothesis: HypothesisOutput) -> StrategySpecification:
        """Return a structured strategy configuration for an approved family."""

    def evaluate_results(self, metrics: dict[str, object]) -> EvaluationOutput:
        """Interpret deterministic metrics without inventing new ones."""

    def critique_experiment(
        self,
        hypothesis: HypothesisOutput,
        strategy: StrategySpecification,
        metrics: dict[str, object],
        evaluation: EvaluationOutput,
    ) -> CriticOutput:
        """Critique the completed experiment."""


class RuleBasedResearchModelClient:
    provider: str = "local"
    model: str = "rule_based_research_v1"
    temperature: float | None = 0.0

    def generate_hypothesis(self, objective: str, symbol: str) -> HypothesisOutput:
        return HypothesisOutput(
            hypothesis=(
                f"{symbol.upper()} may exhibit short-term trend persistence that can be "
                "tested with a moving-average crossover."
            ),
            rationale=(
                "Moving averages convert recent closing prices into a reproducible trend "
                "signal without using future bars."
            ),
            symbol=symbol.upper(),
            strategy_family="moving_average_crossover",
            parameters_to_test={"fast_window": 2, "slow_window": 3},
            expected_behavior=(
                "The strategy should enter after faster trend strength exceeds slower trend "
                "strength and exit when that relationship reverses."
            ),
            failure_conditions=[
                "Negative or weak risk-adjusted returns",
                "Excessive drawdown",
                "Too few trades to learn from the result",
            ],
        )

    def specify_strategy(self, hypothesis: HypothesisOutput) -> StrategySpecification:
        return StrategySpecification(
            strategy=hypothesis.strategy_family,
            symbol=hypothesis.symbol,
            parameters=hypothesis.parameters_to_test,
        )

    def evaluate_results(self, metrics: dict[str, object]) -> EvaluationOutput:
        sharpe = float(cast(SupportsFloat, metrics.get("sharpe_ratio", 0.0)))
        max_dd = float(cast(SupportsFloat, metrics.get("max_drawdown", 0.0)))
        trade_count = int(cast(SupportsInt, metrics.get("number_of_trades", 0)))
        ending_equity = float(cast(SupportsFloat, metrics.get("ending_equity", 0.0)))
        risk_findings: list[str] = []
        if sharpe < 1.0:
            risk_findings.append("Sharpe ratio is below a common exploratory threshold of 1.0.")
        if max_dd < -0.20:
            risk_findings.append("Maximum drawdown is larger than 20%.")
        if trade_count < 2:
            risk_findings.append("Trade count is low, so the sample may not be informative.")
        if not risk_findings:
            risk_findings.append("No obvious first-pass risk threshold was breached.")

        return EvaluationOutput(
            measured_facts=[
                f"Sharpe ratio = {sharpe:.6g}",
                f"Maximum drawdown = {max_dd:.6g}",
                f"Number of trades = {trade_count}",
                f"Ending equity = {ending_equity:.6g}",
            ],
            risk_findings=risk_findings,
            interpretation=(
                "The measured result is an initial deterministic backtest, not proof of a "
                "durable market edge."
            ),
            limitations=[
                "Single symbol",
                "Single parameter set",
                "No walk-forward or out-of-sample validation",
            ],
        )

    def critique_experiment(
        self,
        hypothesis: HypothesisOutput,
        strategy: StrategySpecification,
        metrics: dict[str, object],
        evaluation: EvaluationOutput,
    ) -> CriticOutput:
        _ = (metrics, evaluation)
        return CriticOutput(
            hypothesis_tested=strategy.strategy == hypothesis.strategy_family,
            parameter_assessment=(
                "The parameters are valid for a smoke research run but are not a robustness study."
            ),
            robustness_assessment=(
                "The result is not robust yet because it uses one symbol and one parameter set."
            ),
            methodological_weaknesses=[
                "No benchmark comparison",
                "No parameter sensitivity analysis",
                "No out-of-sample split",
            ],
            lesson=(
                "Mercury can now turn a research objective into a measured experiment while "
                "keeping metrics deterministic."
            ),
            suggested_next_experiment=(
                "Run the same strategy over multiple window pairs and compare against buy and hold."
            ),
        )
