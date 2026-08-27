from pydantic import BaseModel, ConfigDict, Field

from app.ml_research.schemas import MLExperimentDefinition, MLObservation


class MLRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition: MLExperimentDefinition
    observations: list[MLObservation] = Field(min_length=1)
