"""Chooses where cyclone events come from.

`DATA_SOURCE=ibtracs` serves real storms replayed from best-track data and is the
default. It falls back to the synthetic generator only when the archive is
missing, so a fresh checkout still runs — the fallback is reported by
`describe()` rather than hidden.
"""

from app.core.config import settings
from app.services import demo_data, real_data


def using_real_data() -> bool:
    return settings.DATA_SOURCE == "ibtracs" and real_data.available()


def _source():
    return real_data if using_real_data() else demo_data


def summaries() -> list[dict]:
    return _source().summaries()


def event_by_id(cyclone_id) -> dict | None:
    return _source().event_by_id(cyclone_id)


def events() -> list[dict]:
    src = _source()
    return src.events() if hasattr(src, "events") else src.active_events()


def describe() -> dict:
    real = using_real_data()
    return {
        "source": "ibtracs" if real else "synthetic",
        "real_data": real,
        "dataset": real_data.dataset_info() if real else {"available": False},
        "note": (
            "Real historical storms from IBTrACS best track."
            if real
            else "Synthetic events — IBTrACS archive not found; run the ingest step."
        ),
    }
