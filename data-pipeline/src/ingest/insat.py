"""INSAT-3D / 3DR / 3DS fetcher (MOSDAC).

Primary imagery source. TIR-1 carries the cloud-top brightness temperature that
drives eye, CDO and banding structure — everything the identification and
classification models read.

See docs/data-sources.md §1.
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from src.ingest.base import BaseFetcher, FetchResult

# Full-disk scan cadence
SCAN_INTERVAL_MINUTES = 30


class InsatFetcher(BaseFetcher):
    """Downloads INSAT L1B products from MOSDAC.

    Requires a free MOSDAC account; credentials come from the environment.
    """

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        auth = config.get("auth", {})
        self.username = os.getenv(auth.get("username_env", "MOSDAC_USERNAME"), "")
        self.password = os.getenv(auth.get("password_env", "MOSDAC_PASSWORD"), "")
        self.base_url = config.get("base_url", "https://www.mosdac.gov.in")
        self.products = config.get("products", [])
        self.channels = config.get("channels", ["TIR1", "TIR2", "WV"])

    def available_timestamps(self, since: datetime, until: datetime) -> list[datetime]:
        """Scan slots in the window, aligned to the half-hour grid.

        This is the expected schedule; `fetch` still has to handle a slot the
        provider never published.
        """
        timestamps = []
        current = since.replace(
            minute=(since.minute // SCAN_INTERVAL_MINUTES) * SCAN_INTERVAL_MINUTES,
            second=0,
            microsecond=0,
        )
        while current <= until:
            timestamps.append(current)
            current += timedelta(minutes=SCAN_INTERVAL_MINUTES)
        return timestamps

    def fetch(self, timestamp: datetime, destination: Path) -> FetchResult:
        if not self.username or not self.password:
            return FetchResult(
                self.source_id,
                timestamp,
                None,
                status="failed",
                error="MOSDAC credentials not configured",
            )
        # TODO(pipeline): authenticate against MOSDAC, resolve the product URL for
        # this timestamp, stream the HDF5 to disk, verify checksum/size.
        return FetchResult(
            self.source_id,
            timestamp,
            None,
            status="failed",
            error="Not implemented — Phase 1",
        )
