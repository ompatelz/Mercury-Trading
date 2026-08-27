from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.strategy_dsl import StrategyRecord
from app.strategy_dsl.compiler import compile_strategy, explain_strategy
from app.strategy_dsl.schemas import StrategySpec
from app.strategy_dsl.validation import validate_strategy


class StrategyService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, spec: StrategySpec) -> StrategyRecord:
        validate_strategy(spec)
        plan = compile_strategy(spec)
        existing = self.session.scalar(
            select(StrategyRecord).where(StrategyRecord.strategy_hash == plan.strategy_hash)
        )
        if existing is not None:
            return existing
        record = StrategyRecord(
            strategy_hash=plan.strategy_hash,
            dsl_version=spec.dsl_version,
            compiler_version=plan.compiler_version,
            spec=spec.model_dump(mode="json"),
            validation={"status": "accepted", "errors": []},
            complexity=plan.complexity,
            explanation=explain_strategy(spec),
        )
        self.session.add(record)
        self.session.flush()
        return record
