"""Common fetcher interface.

Every satellite source implements this, which is what makes the pipeline
source-pluggable: adding a new satellite is one class plus one entry in
config/sources.yaml, with no changes anywhere else in the system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class FetchResult:
    source_id: str
    timestamp: datetime
    local_path: Path | None
    remote_uri: str | None = None
    status: str = "ok"  # ok | skipped | failed
    error: str | None = None
    size_bytes: int = 0


class BaseFetcher(ABC):
    """Subclass per data source."""

    def __init__(self, config: dict) -> None:
        self.config = config
        self.source_id: str = config["id"]
        self.enabled: bool = config.get("enabled", True)
        self.max_retries: int = config.get("max_retries", 3)

    @abstractmethod
    def available_timestamps(self, since: datetime, until: datetime) -> list[datetime]:
        """List timestamps the provider actually has in this window.

        Providers publish irregularly — never assume a fixed cadence holds.
        """

    @abstractmethod
    def fetch(self, timestamp: datetime, destination: Path) -> FetchResult:
        """Download one product. Must not raise — return a failed FetchResult instead.

        A single bad file must not abort the whole ingestion cycle.
        """

    def fetch_range(self, since: datetime, until: datetime, destination: Path) -> list[FetchResult]:
        """Fetch everything available in a window, skipping what is already on disk."""
        results = []
        for ts in self.available_timestamps(since, until):
            target = destination / self.filename_for(ts)
            if target.exists():
                results.append(
                    FetchResult(
                        self.source_id, ts, target, status="skipped", error="already present"
                    )
                )
                continue
            results.append(self.fetch(ts, destination))
        return results

    def filename_for(self, timestamp: datetime) -> str:
        return f"{self.source_id}_{timestamp:%Y%m%dT%H%M}Z"

    def storage_path(self, root: Path, timestamp: datetime) -> Path:
        """Date-partitioned layout: root/source/YYYY/MM/DD/"""
        return root / self.source_id / f"{timestamp:%Y/%m/%d}"
