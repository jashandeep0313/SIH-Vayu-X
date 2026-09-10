"""Give the siren tower its WiFi credentials, over the cable, once.

The password is typed here and goes straight down the serial port into the
ESP32's NVS. It is never written to a file, never stored in the repo, never
passed on a command line where a shell history would keep it, and never shown
on screen. After this the tower is reachable over the network and further
firmware updates go over the air — this should be the last time it needs a
cable.

    python scripts/provision_siren_wifi.py

The ESP32 is 2.4 GHz only. A 5 GHz network will not be found, which is the
usual reason this appears to fail.
"""

from __future__ import annotations

import sys
import time
from getpass import getpass

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    sys.exit("pyserial is required:  pip install pyserial")

BAUD = 115200
KNOWN_VIDS = {0x1A86, 0x10C4, 0x0403, 0x303A}


def find_port() -> str | None:
    for p in list_ports.comports():
        if p.vid in KNOWN_VIDS:
            return p.device
    return None


def command(conn: serial.Serial, line: str, wait: float = 0.4) -> str:
    conn.reset_input_buffer()
    conn.write(f"{line}\n".encode())
    conn.flush()
    time.sleep(wait)
    return conn.readline().decode(errors="replace").strip()


def main() -> None:
    port = sys.argv[1] if len(sys.argv) > 1 else find_port()
    if not port:
        sys.exit(
            "No ESP32 found. Plug it in over USB (a DATA cable), or pass the port:\n"
            "    python scripts/provision_siren_wifi.py COM7"
        )

    print(f"Using {port}")
    conn = serial.Serial()
    conn.port, conn.baudrate, conn.timeout = port, BAUD, 2
    conn.dtr = conn.rts = False
    conn.open()
    time.sleep(0.4)

    reply = command(conn, "PING")
    if not reply.startswith("PONG"):
        conn.close()
        sys.exit(
            f"The tower did not answer PING (got {reply!r}).\n"
            "Flash hardware/esp32_siren first, then run this again."
        )
    print(f"Tower: {reply}")
    if "2." not in reply:
        print("  ! This looks like firmware v1, which has no WiFi. Reflash v2 first.")

    ssid = input("WiFi SSID (2.4 GHz only): ").strip()
    if not ssid:
        conn.close()
        sys.exit("No SSID given, nothing changed.")
    if " " in ssid:
        print("  note: the SSID contains a space; that is fine, the password is read to end of line")
    password = getpass("WiFi password (not shown, not stored): ")

    print(command(conn, f"WIFI {ssid} {password}"))
    del password  # no reason to keep it in memory a moment longer

    print("Rebooting the tower…")
    conn.setDTR(False)
    conn.setRTS(True)
    time.sleep(0.2)
    conn.setRTS(False)

    # Watch it come up and report where it landed.
    deadline = time.time() + 20
    ip = None
    while time.time() < deadline:
        line = conn.readline().decode(errors="replace").strip()
        if not line:
            continue
        if line.startswith(("WIFI", "MDNS", "READY", "OK ")):
            print(f"  {line}")
        if line.startswith("OK STA "):
            ip = line.split()[2]
            break
        if line.startswith("OK AP "):
            print("\n  Could not join that network — the tower fell back to its own")
            print("  access point instead. Check the SSID, the password, and that")
            print("  the network is 2.4 GHz. Connect to 'Vayu-X-Siren' to reach it.")
            break

    conn.close()

    if ip:
        print(f"\nTower is on the network at {ip}")
        print("Verify with:")
        print(f"    curl http://{ip}/ping")
        print("Then point the alert service at it:")
        print(f"    SIREN_HOST={ip}       (in .env)")
        print("\nYou can unplug the USB cable now. Future firmware updates go over the air.")


if __name__ == "__main__":
    main()
