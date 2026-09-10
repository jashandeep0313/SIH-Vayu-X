"""Last-mile siren tower over a USB serial link.

Why this exists as a separate path from SMS: a cyclone warning that depends on
the cellular network fails exactly where it matters most. The stretch of coast
between Paradip and Gopalpur loses tower coverage in the hours before landfall,
and that is the population you most need to reach. A physical siren driven by a
local microcontroller keeps working with no network at all.

Topology in the demo:

    model (:8001) -> backend (:8000) -> alert-system (:8002) -> USB -> ESP32
                                                                        |
                                                          traffic-light LEDs
                                                          + piezo siren

In a real deployment the last hop is LoRa (433 MHz, several km on flat coast),
not USB. The serial link here stands in for that radio hop so the rest of the
chain can be built and demonstrated honestly. See docs/alerting.md.

Guards, deliberately different from the SMS path:
  * SMS is manual because it costs credits and texts real people. A siren costs
    nothing per sounding, and a tower that waits for a human defeats the point,
    so it *may* fire automatically.
  * But it is disabled by default (`SIREN_ENABLED`), because a siren that
    starts wailing during setup is how a demo goes wrong.
  * Every sounding has a hard duration cap, so a dropped link cannot leave it
    screaming.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import time
from dataclasses import dataclass

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pyserial is optional — the service must still start
    serial = None
    list_ports = None

BAUD = 115200
# Serial adapters found on ESP32 dev boards. Matching on VID avoids grabbing an
# unrelated COM port (a Bluetooth bridge, a printer) and blasting bytes at it.
KNOWN_VIDS = {
    0x1A86: "CH340/CH341",
    0x10C4: "CP210x",
    0x0403: "FTDI",
    0x303A: "Espressif native USB",
}

SIREN_ENABLED = os.getenv("SIREN_ENABLED", "false").lower() == "true"
MAX_DURATION_S = int(os.getenv("SIREN_MAX_SECONDS", "30"))
PORT_OVERRIDE = os.getenv("SIREN_PORT")  # e.g. COM5, /dev/ttyUSB0

# Category -> what the tower should do. Mirrors SEVERITY_FOR in manual_sms.py.
SEVERITY_FOR = {
    "SCS": "YELLOW",
    "VSCS": "ORANGE",
    "ESCS": "RED",
    "SuCS": "RED",
}
ALERTABLE = set(SEVERITY_FOR)


@dataclass
class DeviceStatus:
    connected: bool
    port: str | None = None
    adapter: str | None = None
    firmware: str | None = None
    error: str | None = None


def available_ports() -> list[dict]:
    """Every serial port the OS can see, annotated with whether it looks like an ESP32."""
    if list_ports is None:
        return []
    out = []
    for p in list_ports.comports():
        out.append(
            {
                "port": p.device,
                "description": p.description,
                "vid": f"0x{p.vid:04X}" if p.vid else None,
                "adapter": KNOWN_VIDS.get(p.vid) if p.vid else None,
                "likely_esp32": p.vid in KNOWN_VIDS if p.vid else False,
            }
        )
    return out


def find_port() -> str | None:
    """Pick the ESP32's port. An explicit SIREN_PORT always wins."""
    if PORT_OVERRIDE:
        return PORT_OVERRIDE
    if list_ports is None:
        return None
    for p in list_ports.comports():
        if p.vid in KNOWN_VIDS:
            return p.device
    return None


class SirenTower:
    """One serial-attached siren tower.

    The connection is opened lazily and kept open: reopening on every alert
    would reset the board (DTR toggling drives the ESP32 auto-reset circuit)
    and cost ~2 s of boot time on the one request that must not be slow.
    """

    def __init__(self) -> None:
        self._conn = None
        self._port: str | None = None
        self._firmware: str | None = None
        self._sounding_until: float = 0.0

    # ---------------------------------------------------------------- link
    def connect(self) -> DeviceStatus:
        if serial is None:
            return DeviceStatus(False, error="pyserial not installed (pip install pyserial)")

        if self._conn is not None and self._conn.is_open:
            return DeviceStatus(True, self._port, firmware=self._firmware)

        port = find_port()
        if port is None:
            return DeviceStatus(
                False,
                error="no ESP32-like serial port found. Check the cable is a DATA "
                "cable, not charge-only, and that the CH340/CP210x driver is installed.",
            )

        try:
            conn = serial.Serial()
            conn.port = port
            conn.baudrate = BAUD
            conn.timeout = 2
            conn.write_timeout = 2
            # Hold both low so opening the port does not yank the board into
            # reset or into the ROM bootloader.
            conn.dtr = False
            conn.rts = False
            conn.open()
        except Exception as exc:  # noqa: BLE001 - surfaced to the operator
            return DeviceStatus(False, port, error=f"could not open {port}: {exc}")

        self._conn, self._port = conn, port
        time.sleep(0.3)
        conn.reset_input_buffer()

        reply = self._command("PING")
        self._firmware = reply if reply and reply.startswith("PONG") else None
        if self._firmware is None:
            return DeviceStatus(
                True,
                port,
                error=f"port open but firmware did not answer PING (got {reply!r}). "
                "Is esp32_siren.ino flashed?",
            )
        return DeviceStatus(True, port, firmware=self._firmware)

    def _command(self, line: str) -> str | None:
        """Write one line, read one line. Never raises — the caller reports."""
        if self._conn is None or not self._conn.is_open:
            return None
        try:
            self._conn.reset_input_buffer()
            self._conn.write(f"{line}\n".encode())
            self._conn.flush()
            return self._conn.readline().decode(errors="replace").strip()
        except Exception:  # noqa: BLE001
            with contextlib.suppress(Exception):
                self._conn.close()
            self._conn = None
            return None

    def close(self) -> None:
        if self._conn is not None and self._conn.is_open:
            self._command("STOP")
            self._conn.close()
        self._conn = None

    # -------------------------------------------------------------- status
    def status(self) -> dict:
        st = self.connect()
        return {
            "enabled": SIREN_ENABLED,
            "connected": st.connected,
            "port": st.port,
            "firmware": st.firmware,
            "error": st.error,
            "sounding": time.time() < self._sounding_until,
            "max_seconds": MAX_DURATION_S,
            "ports_seen": available_ports(),
        }

    # --------------------------------------------------------------- fire
    def sound(
        self,
        category: str,
        seconds: int = 10,
        confirm: bool = False,
        auto: bool = False,
    ) -> dict:
        """Sound the tower for `category`.

        `auto=True` is the automatic path taken when a classification clears the
        threshold. `confirm=True` is an operator pressing the button. One of the
        two is required, so a stray request cannot set it off.
        """
        if not (confirm or auto):
            return {"sounded": False, "reason": "confirm=true or auto=true required"}

        if not SIREN_ENABLED:
            return {
                "sounded": False,
                "reason": "siren disabled — set SIREN_ENABLED=true in alert-system/.env",
            }

        severity = SEVERITY_FOR.get(category)
        if severity is None:
            return {
                "sounded": False,
                "reason": f"{category} is below the siren threshold "
                f"(sounds at {', '.join(sorted(ALERTABLE))})",
            }

        seconds = max(1, min(int(seconds), MAX_DURATION_S))

        st = self.connect()
        if not st.connected:
            return {"sounded": False, "reason": st.error, "port": st.port}

        reply = self._command(f"ALERT {severity} {category} {seconds}")
        if reply is None or not reply.startswith("OK"):
            return {
                "sounded": False,
                "reason": f"device did not acknowledge (got {reply!r})",
                "port": st.port,
            }

        self._sounding_until = time.time() + seconds
        return {
            "sounded": True,
            "severity": severity,
            "category": category,
            "seconds": seconds,
            "port": st.port,
            "trigger": "automatic" if auto else "operator",
        }

    def all_clear(self) -> dict:
        st = self.connect()
        if not st.connected:
            return {"ok": False, "reason": st.error}
        self._sounding_until = 0.0
        reply = self._command("STOP")
        return {"ok": bool(reply and reply.startswith("OK")), "reply": reply}

    def self_test(self) -> dict:
        """Cycle the lamps and chirp once — proves the tower works before a demo."""
        st = self.connect()
        if not st.connected:
            return {"ok": False, "reason": st.error, "ports_seen": available_ports()}
        reply = self._command("TEST")
        return {"ok": bool(reply and reply.startswith("OK")), "reply": reply, "port": st.port}


tower = SirenTower()


async def sound_async(category: str, seconds: int = 10, **kw) -> dict:
    """Serial I/O is blocking; keep it off the event loop."""
    return await asyncio.to_thread(tower.sound, category, seconds, **kw)
