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

import httpx

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

# Network transport. When set, the tower is reached over WiFi and no cable is
# needed; the command strings are identical either way. `vayux-siren.local`
# works wherever mDNS resolves, an IP address always works.
SIREN_HOST = os.getenv("SIREN_HOST", "").strip()
HTTP_TIMEOUT = float(os.getenv("SIREN_HTTP_TIMEOUT", "6"))
# Probing hosts that are not there is the slow path, and the dashboard polls
# status on every load. A tower on the LAN answers in milliseconds, so a short
# probe loses nothing real and keeps a missing tower from costing ten seconds.
DISCOVERY_TIMEOUT = float(os.getenv("SIREN_DISCOVERY_TIMEOUT", "1.5"))
AP_FALLBACK_HOST = "192.168.4.1"  # the tower's own access point

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


def _http_candidates() -> list[str]:
    """Hosts to try, most specific first."""
    hosts = []
    if SIREN_HOST:
        hosts.append(SIREN_HOST)
    hosts += ["vayux-siren.local", AP_FALLBACK_HOST]
    return hosts


class SirenTower:
    """One siren tower, reachable over WiFi or over a USB cable.

    Network first when a host is configured, cable otherwise. The command
    strings are identical across both, which is the whole reason the protocol is
    plain text — the same code will drive it over LoRa later without changing.

    The serial connection is opened lazily and kept open: reopening on every
    alert would reset the board (DTR toggling drives the ESP32 auto-reset
    circuit) and cost ~2 s of boot time on the one request that must not be slow.
    """

    def __init__(self) -> None:
        self._conn = None
        self._port: str | None = None
        self._firmware: str | None = None
        self._sounding_until: float = 0.0
        self._host: str | None = None
        self._transport: str = "none"

    # ------------------------------------------------------------ network
    def _http(self, command: str) -> tuple[str | None, str | None]:
        """Send one command over HTTP. Returns (reply, host) or (None, None)."""
        known = bool(self._host)
        hosts = [self._host] if known else _http_candidates()
        timeout = HTTP_TIMEOUT if known else DISCOVERY_TIMEOUT
        for host in hosts:
            if not host:
                continue
            try:
                r = httpx.get(
                    f"http://{host}/cmd",
                    params={"q": command},
                    timeout=timeout,
                )
                if r.status_code == 200:
                    self._host = host
                    return r.text.strip(), host
            except Exception:  # noqa: BLE001 - any failure just means try the next
                continue
        self._host = None
        return None, None

    # ---------------------------------------------------------------- link
    def connect(self) -> DeviceStatus:
        # Network transport wins when it answers: it is the deployment shape,
        # and it means the tower can sit anywhere with a power bank.
        reply, host = self._http("PING")
        if reply and reply.startswith("PONG"):
            self._transport = "wifi"
            self._firmware = reply
            return DeviceStatus(True, host, adapter="wifi", firmware=reply)

        if serial is None:
            return DeviceStatus(False, error="pyserial not installed (pip install pyserial)")

        if self._conn is not None and self._conn.is_open:
            return DeviceStatus(True, self._port, firmware=self._firmware)

        port = find_port()
        if port is None:
            return DeviceStatus(
                False,
                error=(
                    "tower not reachable. Over WiFi: set SIREN_HOST to its IP (run "
                    "scripts/provision_siren_wifi.py once over USB to give it credentials). "
                    "Over USB: check the cable is a DATA cable, not charge-only, and that "
                    "the CH340/CP210x driver is installed."
                ),
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
        self._transport = "serial"
        return DeviceStatus(True, port, adapter="serial", firmware=self._firmware)

    def _command(self, line: str) -> str | None:
        """Send one command over whichever transport is live.

        Never raises — the caller reports. If the network transport is in use it
        is tried first and the cable is not touched at all.
        """
        if self._transport == "wifi":
            reply, _ = self._http(line)
            if reply is not None:
                return reply
            # The tower moved, slept, or the network dropped. Fall through and
            # let the serial path try, rather than reporting a dead tower that
            # is sitting on the desk plugged in.
            self._transport = "none"

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
        """Release the tower. Silences it first — never leave one sounding."""
        if self._transport == "wifi":
            self._http("STOP")
        elif self._conn is not None and self._conn.is_open:
            self._command("STOP")
        if self._conn is not None and self._conn.is_open:
            self._conn.close()
        self._conn = None
        self._transport = "none"
        self._host = None

    # -------------------------------------------------------------- status
    def status(self) -> dict:
        st = self.connect()
        net = self._command("NET") if st.connected else None
        return {
            "enabled": SIREN_ENABLED,
            "connected": st.connected,
            "transport": self._transport,
            "port": st.port,
            "host": self._host,
            "network": net,
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


# Both transports block: pyserial always, and httpx here is the sync client so
# one code path serves both. Every entry point therefore hands off to a thread —
# discovery alone can spend several seconds failing over candidate hosts, and
# that must never stall the service that is meant to be dispatching warnings.
async def sound_async(category: str, seconds: int = 10, **kw) -> dict:
    return await asyncio.to_thread(tower.sound, category, seconds, **kw)


async def status_async() -> dict:
    return await asyncio.to_thread(tower.status)


async def self_test_async() -> dict:
    return await asyncio.to_thread(tower.self_test)


async def all_clear_async() -> dict:
    return await asyncio.to_thread(tower.all_clear)
