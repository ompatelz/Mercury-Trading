from sqlalchemy.orm import Session

from app.agents.service import AgentVersionService
from app.core.config import get_settings
from app.memory.service import ResearchMemoryService
from app.model_routing.client import RoutingResearchModelClient
from app.model_routing.evidence import EvalEvidenceService
from app.model_routing.registry import ModelRegistry
from app.model_routing.schemas import ModelCapability, RoutingPolicy
from app.model_routing.service import ModelRouter
from app.model_routing.tracking import ModelUsageService
from app.models.agent import ResearchTraceEvent
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
        self.model_client: ResearchModelClient
        if model_client is None:
            delegate = RuleBasedResearchModelClient()
            registry = ModelRegistry(
                [
                    ModelCapability(
                        model_id=delegate.model,
                        provider=delegate.provider,
                        version="v1",
                        context_window=0,
                        supports_structured_output=True,
                        supports_tools=False,
                    )
                ]
            )
            policy = RoutingPolicy(get_settings().routing_policy)
            self.model_client = RoutingResearchModelClient(
                delegate, ModelRouter(registry, EvalEvidenceService(session).benchmarks()), policy
            )
        else:
            self.model_client = model_client

    def run_research_experiment(self, request: ResearchExperimentRequest) -> ResearchExperiment:
        version_service = AgentVersionService(self.session)
        agent_version = version_service.ensure_default_agent()
        workflow_version = version_service.ensure_default_workflow()
        memory_service = ResearchMemoryService(self.session)
        retrieved_memory = memory_service.retrieve_for_research(
            objective=request.objective,
            symbol=request.symbol,
            top_k=int(workflow_version.retrieval_config.get("top_k", 3)),
        )
        state = run_research_workflow(
            request=request,
            session=self.session,
            model_client=self.model_client,
            retrieved_memory=[
                {
                    "lesson_id": str(item.lesson_id),
                    "source_experiment_id": str(item.source_experiment_id),
                    "similarity": item.similarity,
                    "summary": item.summary,
                    "tags": item.tags,
                }
                for item in retrieved_memory
            ],
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

        model_metadata = build_model_metadata(state, self.model_client).model_dump(mode="json")
        model_metadata["agent_version"] = f"{agent_version.name}:{agent_version.version}"
        workflow_metadata = {
            "workflow_run_id": state.workflow_run_id,
            "workflow_version": f"{workflow_version.name}:{workflow_version.version}",
            "node_durations_ms": state.node_durations_ms,
            "tool_calls": 1,
            "retrieved_memory": state.retrieved_memory,
            "retrieved_memory_count": len(state.retrieved_memory),
        }
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
            model_metadata=model_metadata,
            workflow_metadata=workflow_metadata,
            error_message=None,
            agent_version_id=agent_version.id,
            workflow_version_id=workflow_version.id,
        )
        self.session.add(record)
        self.session.flush()
        if isinstance(self.model_client, RoutingResearchModelClient):
            usage = ModelUsageService(self.session)
            for invocation in self.model_client.invocations:
                usage.record(
                    invocation.decision,
                    agent=invocation.agent,
                    success=invocation.success,
                    latency_ms=invocation.latency_ms,
                    research_experiment_id=record.id,
                    workflow_version_id=workflow_version.id,
                )
        lesson = memory_service.create_lesson(record)
        self.session.add_all(
            [
                ResearchTraceEvent(
                    research_experiment_id=record.id,
                    workflow_run_id=state.workflow_run_id,
                    event_type="memory_retrieved",
                    event_payload={"items": state.retrieved_memory},
                ),
                ResearchTraceEvent(
                    research_experiment_id=record.id,
                    workflow_run_id=state.workflow_run_id,
                    event_type="lesson_created",
                    event_payload={
                        "lesson_id": str(lesson.id),
                        "tags": lesson.tags,
                        "market_regime": lesson.market_regime,
                    },
                ),
            ]
        )
        self.session.flush()
        self.session.refresh(record)
        return record
