from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.experiment import Experiment


class ExperimentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, experiment: Experiment) -> Experiment:
        self.session.add(experiment)
        self.session.flush()
        self.session.refresh(experiment)
        return experiment

    def get(self, experiment_id: UUID) -> Experiment | None:
        return self.session.scalar(select(Experiment).where(Experiment.id == experiment_id))
