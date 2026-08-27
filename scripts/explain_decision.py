import argparse
import json
from uuid import UUID

from app.db.session import SessionLocal
from app.governance.service import DecisionService


def main() -> int:
    parser = argparse.ArgumentParser(description="Explain a persisted Mercury research decision.")
    parser.add_argument("decision_id")
    args = parser.parse_args()
    with SessionLocal() as session:
        decision = DecisionService(session).explain(UUID(args.decision_id))
    if decision is None:
        parser.error("decision not found")
    print(json.dumps(decision, default=str, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
