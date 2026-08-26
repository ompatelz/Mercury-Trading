"""Compare two real benchmark captures without inventing performance conclusions."""

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("succeeded_jobs") or payload.get("failed_jobs"):
        raise ValueError(f"{path} is not a successful, non-empty measurement")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare measured sequential and parallel runs.")
    parser.add_argument("--sequential", type=Path, required=True)
    parser.add_argument("--parallel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    sequential = _load(args.sequential)
    parallel = _load(args.parallel)
    if sequential["succeeded_jobs"] != parallel["succeeded_jobs"]:
        raise ValueError("runs must contain the same number of succeeded jobs")
    speedup = sequential["wall_clock_seconds"] / parallel["wall_clock_seconds"]
    result = {
        "sequential": sequential,
        "parallel": parallel,
        "measured_speedup": round(speedup, 6),
        "comparison_note": (
            "Measured locally from the supplied captures; hardware and workload apply."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
