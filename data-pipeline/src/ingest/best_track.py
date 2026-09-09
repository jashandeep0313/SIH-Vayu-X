"""IBTrACS best-track ingestion.

IBTrACS (NOAA NCEI) is the merged global best-track archive. Unlike INSAT imagery
it is public and needs no credentials, which makes it the one real dataset we can
train on immediately.

Parsing lives in best_track_parsing.py so ai-model can reuse it during training
without dragging in the fetcher framework.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from src.ingest.base import BaseFetcher, FetchResult
from src.ingest.best_track_parsing import categorise, load_best_track, track_summary

logger = logging.getLogger("vayux.ingest.best_track")

IBTRACS_BASE = (
    "https://www.ncei.noaa.gov/data/"
    "international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv"
)

__all__ = ["BestTrackFetcher", "categorise", "load_best_track", "track_summary"]

class BestTrackFetcher(BaseFetcher):
    """Downloads and normalises an IBTrACS basin subset."""

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.basin = config.get("basin", "NI")  # NI = North Indian
        self.url = config.get("url") or f"{IBTRACS_BASE}/ibtracs.{self.basin}.list.v04r01.csv"

    def available_timestamps(self, since: datetime, until: datetime) -> list[datetime]:
        """IBTrACS ships as one whole-archive file, so there is a single artifact."""
        return [until]

    def fetch(self, timestamp: datetime, destination: Path) -> FetchResult:
        import httpx

        destination.mkdir(parents=True, exist_ok=True)
        target = destination / f"ibtracs_{self.basin}_v04r01.csv"
        try:
            with httpx.stream("GET", self.url, timeout=180, follow_redirects=True) as r:
                r.raise_for_status()
                with open(target, "wb") as f:
                    for chunk in r.iter_bytes(1 << 16):
                        f.write(chunk)
        except Exception as exc:  # never raise: one bad source must not abort a cycle
            return FetchResult(self.source_id, timestamp, None, status="failed", error=str(exc))

        return FetchResult(
            self.source_id, timestamp, target, status="ok", size_bytes=target.stat().st_size
        )
