import argparse
import json
from typing import Any
from uuid import UUID

from app.db.session import SessionLocal
from app.research_artifacts.service import ResearchArtifactService


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproduce a persisted Mercury experiment.")
    parser.add_argument("experiment_id", type=UUID)
    args = parser.parse_args()

    with SessionLocal() as session:
        result = ResearchArtifactService(session).reproduce_experiment(args.experiment_id)
    print(json.dumps(_json_safe(result), indent=2, sort_keys=True))


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


if __name__ == "__main__":
    main()
