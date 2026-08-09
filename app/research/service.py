from sqlalchemy.orm import Session

from app.models.experiment import ResearchExperiment
from app.research.model_client import ResearchModelClient, RuleBasedResearchModelClient
from app.research.schemas import ResearchExperimentRequest
from app.research.workflow import build_model_metadata, run_research_workflow


class ResearchExperimentService:
    def __init__(
        self,
        session: Session,
        model_client: ResearchModelClient | None = None,
    ) -> None:
        self.session = session
        if model_client is None:
            self.model_client: ResearchModelClient = RuleBasedResearchModelClient()
        else:
            self.model_client = model_client

    def run_research_experiment(self, request: ResearchExperimentRequest) -> ResearchExperiment:
        state = run_research_workflow(
            request=request,
            session=self.session,
            model_client=self.model_client,
        )
        if (
            state.hypothesis is None
            or state.strategy is None
            or state.backtest is None
            or state.evaluation is None
            or state.critique is None
            or state.report is None
        ):
            raise ValueError("research workflow did not complete")

        record = ResearchExperiment(
            objective=request.objective,
            symbol=request.symbol.upper(),
            start_date=request.start_date,
            end_date=request.end_date,
            interval=request.interval,
            execution_engine=request.execution_engine,
            status="completed",
            hypothesis=state.hypothesis.model_dump(mode="json"),
            strategy=state.strategy.model_dump(mode="json"),
            backtest_experiment_id=state.backtest.experiment_id,
            metrics=state.backtest.metrics,
            evaluation=state.evaluation.model_dump(mode="json"),
            critique=state.critique.model_dump(mode="json"),
            report=state.report.model_dump(mode="json"),
            model_metadata=build_model_metadata(state, self.model_client).model_dump(mode="json"),
            workflow_metadata={
                "workflow_run_id": state.workflow_run_id,
                "node_durations_ms": state.node_durations_ms,
                "tool_calls": 1,
            },
            error_message=None,
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return record
