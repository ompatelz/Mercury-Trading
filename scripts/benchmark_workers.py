"""Record actual completion timing for an already-running local worker pool."""

import argparse
import json
import time
from pathlib import Path

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.campaign import CampaignJob


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure an already-running Mercury worker pool.")
    parser.add_argument("campaign_id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--poll-seconds", type=float, default=0.5)
    args = parser.parse_args()

    start = time.perf_counter()
    while True:
        with SessionLocal() as session:
            rows = session.execute(
                select(CampaignJob.status, func.count())
                .where(CampaignJob.campaign_id == args.campaign_id)
                .group_by(CampaignJob.status)
            ).all()
        counts = {status: count for status, count in rows}
        active = counts.get("QUEUED", 0) + counts.get("RETRYING", 0) + counts.get("RUNNING", 0)
        if active == 0:
            break
        time.sleep(args.poll_seconds)

    elapsed = time.perf_counter() - start
    completed = counts.get("SUCCEEDED", 0)
    payload = {
        "campaign_id": args.campaign_id,
        "wall_clock_seconds": round(elapsed, 6),
        "succeeded_jobs": completed,
        "failed_jobs": counts.get("FAILED", 0),
        "throughput_jobs_per_second": round(completed / elapsed, 6) if elapsed else None,
        "status_counts": counts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
