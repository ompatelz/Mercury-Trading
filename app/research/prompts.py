from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    text: str


HYPOTHESIS_PROMPT = PromptTemplate(
    version="hypothesis_v1",
    text=(
        "Generate one testable quant hypothesis. Return only structured fields. "
        "Use approved strategy families and avoid claiming measured results."
    ),
)

STRATEGY_PROMPT = PromptTemplate(
    version="strategy_spec_v1",
    text=(
        "Convert the hypothesis into an approved Mercury strategy specification. "
        "Return only a registered strategy name and validated parameters."
    ),
)

EVALUATION_PROMPT = PromptTemplate(
    version="evaluation_v1",
    text=(
        "Interpret deterministic backtest metrics. Do not invent metrics. "
        "Separate measured facts from interpretation."
    ),
)

CRITIC_PROMPT = PromptTemplate(
    version="critic_v1",
    text=(
        "Critique whether the experiment actually tested the hypothesis and "
        "recommend one next experiment."
    ),
)
