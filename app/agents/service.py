from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import AgentVersion, WorkflowVersion

DEFAULT_AGENT_VERSION = "research_agent:v1"
DEFAULT_WORKFLOW_VERSION = "research_workflow:v1"


class AgentVersionService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_agent(self) -> AgentVersion:
        existing = self.session.scalar(
            select(AgentVersion).where(
                AgentVersion.name == "research_agent",
                AgentVersion.version == "v1",
            )
        )
        if existing is not None:
            return existing
        record = AgentVersion(
            name="research_agent",
            version="v1",
            role="hypothesis_strategy_evaluation_critic",
            model="rule_based_research_v1",
            prompt_version="v1",
            config={"temperature": 0.0, "mode": "deterministic"},
            status="active",
        )
        self.session.add(record)
        self.session.flush()
        return record

    def ensure_default_workflow(self) -> WorkflowVersion:
        existing = self.session.scalar(
            select(WorkflowVersion).where(
                WorkflowVersion.name == "research_workflow",
                WorkflowVersion.version == "v1",
            )
        )
        if existing is not None:
            return existing
        record = WorkflowVersion(
            name="research_workflow",
            version="v1",
            backtester_version="moving_average_backtester:v1",
            retrieval_config={"top_k": 3, "min_similarity": 0.05},
            tool_versions={"backtest_tool": "v1", "lesson_extractor": "v1"},
            manifest={
                "components": {
                    "hypothesis_agent": {"version": "v1", "prompt": "hypothesis_v1"},
                    "strategy_generation_agent": {"version": "v1", "prompt": "strategy_spec_v1"},
                    "critic": {"version": "v1", "prompt": "critic_v1"},
                    "memory_retrieval": {"version": "hashed_embedding_v1", "top_k": 3},
                    "research_orchestrator": {"version": "v1"},
                },
                "model": {
                    "provider": "local",
                    "name": "rule_based_research_v1",
                    "temperature": 0.0,
                },
                "tools": {"backtest_tool": "v1", "lesson_extractor": "v1"},
                "workflow": {"memory_enabled": True, "retry_count": 0},
            },
            status="active",
        )
        self.session.add(record)
        self.session.flush()
        return record

    def list_agent_versions(self) -> list[AgentVersion]:
        return list(self.session.scalars(select(AgentVersion).order_by(AgentVersion.created_at)))

    def list_workflow_versions(self) -> list[WorkflowVersion]:
        return list(
            self.session.scalars(select(WorkflowVersion).order_by(WorkflowVersion.created_at))
        )
