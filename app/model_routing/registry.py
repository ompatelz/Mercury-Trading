from collections.abc import Iterable

from app.model_routing.schemas import ModelCapability


class ModelRegistry:
    """Small, explicit registry; provider strings live only in model records."""

    def __init__(self, models: Iterable[ModelCapability] = ()) -> None:
        self._models = {model.model_id: model for model in models}

    def register(self, model: ModelCapability) -> None:
        if model.model_id in self._models:
            raise ValueError(f"model already registered: {model.model_id}")
        self._models[model.model_id] = model

    def get(self, model_id: str) -> ModelCapability:
        try:
            return self._models[model_id]
        except KeyError as exc:
            raise ValueError(f"unknown model: {model_id}") from exc

    def enabled(self) -> list[ModelCapability]:
        return [model for model in self._models.values() if model.enabled]
