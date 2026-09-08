"""Ingestion scheduler.

Runs the fetch → transform → load cycle on a cron schedule matching the INSAT
full-disk cadence, then notifies the model service that a new frame is available.

    python -m src.scheduler          # run continuously
    python -m src.scheduler --once   # single cycle (development / manual backfill)
"""

import argparse
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(name)s: %(message)s")
logger = logging.getLogger("vayux.pipeline")

FETCHER_REGISTRY: dict[str, type] = {}


def _register_fetchers() -> None:
    """Map fetcher names in sources.yaml to their classes."""
    from src.ingest.insat import InsatFetcher

    FETCHER_REGISTRY["InsatFetcher"] = InsatFetcher
    # TODO(pipeline): ScatterometerFetcher, ImergFetcher, Era5Fetcher, BestTrackFetcher


def load_config(path: str | Path = "config/sources.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def run_cycle(config: dict) -> None:
    """One full ingestion cycle across every enabled source."""
    schedule = config.get("schedule", {})
    lookback = timedelta(hours=schedule.get("lookback_hours", 6))
    until = datetime.now(UTC)
    since = until - lookback

    raw_root = Path(config["storage"]["local_raw"])
    sources = [s for s in config.get("sources", []) if s.get("enabled", True)]
    sources.sort(key=lambda s: s.get("priority", 99))

    logger.info("Ingestion cycle %s → %s across %d sources", since, until, len(sources))

    for source in sources:
        fetcher_cls = FETCHER_REGISTRY.get(source.get("fetcher", ""))
        if fetcher_cls is None:
            logger.warning("No fetcher registered for source '%s' — skipping", source["id"])
            continue

        fetcher = fetcher_cls(source)
        destination = raw_root / source["id"]
        destination.mkdir(parents=True, exist_ok=True)

        # One failing source must never abort the cycle — a scatterometer outage
        # should not stop INSAT imagery from being ingested.
        try:
            results = fetcher.fetch_range(since, until, destination)
        except Exception:
            logger.exception("Source '%s' failed", source["id"])
            continue

        ok = sum(1 for r in results if r.status == "ok")
        logger.info("  %s: %d fetched, %d total", source["id"], ok, len(results))

    # TODO(pipeline): transform new files, load to MinIO + PostGIS,
    # then POST /infer on the model service for each new frame.


def main() -> None:
    parser = argparse.ArgumentParser(description="Vayu-X satellite ingestion pipeline")
    parser.add_argument("--config", default="config/sources.yaml")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    args = parser.parse_args()

    _register_fetchers()
    config = load_config(args.config)

    if args.once:
        run_cycle(config)
        return

    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    cron = config.get("schedule", {}).get("cron", "*/30 * * * *")
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_cycle, CronTrigger.from_crontab(cron), args=[config])
    logger.info("Scheduler started with cron '%s'", cron)
    scheduler.start()


if __name__ == "__main__":
    main()
