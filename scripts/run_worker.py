import argparse
import time

from app.campaigns.service import CampaignService
from app.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Mercury campaign jobs.")
    parser.add_argument("--worker-name", default="campaign-worker")
    parser.add_argument("--max-jobs", type=int, default=0, help="0 means run continuously")
    parser.add_argument("--idle-sleep", type=float, default=1.0)
    args = parser.parse_args()

    processed = 0
    while args.max_jobs == 0 or processed < args.max_jobs:
        with SessionLocal() as session:
            service = CampaignService(session)
            job = service.process_next_job(args.worker_name)
            session.commit()
        if job is None:
            if args.max_jobs:
                break
            time.sleep(args.idle_sleep)
            continue
        processed += 1


if __name__ == "__main__":
    main()
