"""
SYLION Devices -- Device Discovery Service (M1)

Scans for devices on various transports, creates stub entries for
simulated devices, and emits device.attached / device.released events.
"""

import json
import logging
import re
import socket
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("sylion.devices.device_discovery")


class DeviceDiscoveryService:
    """Discovers devices on available transports and tracks their status."""

    def __init__(self, db_path: str | Path | None = None, event_bus=None):
        self._event_bus = event_bus
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        if self._db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS discovered_devices (
                    device_id     TEXT PRIMARY KEY,
                    transport     TEXT NOT NULL DEFAULT '',
                    model         TEXT NOT NULL DEFAULT '',
                    firmware      TEXT NOT NULL DEFAULT '',
                    capabilities  TEXT NOT NULL DEFAULT '{}',
                    status        TEXT NOT NULL DEFAULT 'detected',
                    discovered_at REAL NOT NULL
                )
            """)
            self._conn.commit()

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def scan(self, transport: str = "all") -> list[dict]:
        """Scan for real devices on available transports.

        Checks ADB for Android devices, scans for SSH-accessible hosts,
        and falls back to stub entries if no real devices found.
        """
        discovered = []

        if transport in ("all", "usb"):
            discovered.extend(self._scan_adb())

        if transport in ("all", "wifi"):
            discovered.extend(self._scan_network())

        # Persist discovered devices
        for dev in discovered:
            now = time.time()
            with self._lock:
                self._conn.execute("""
                    INSERT OR IGNORE INTO discovered_devices
                    (device_id, transport, model, firmware, capabilities, status, discovered_at)
                    VALUES (?, ?, ?, ?, ?, 'detected', ?)
                """, (dev["device_id"], dev["transport"], dev.get("model", ""),
                      dev.get("firmware", ""), json.dumps(dev.get("capabilities", {})), now))
                self._conn.commit()
            dev["discovered_at"] = now
            dev["status"] = "detected"
            self._emit("device.attached", {
                "device_id": dev["device_id"],
                "transport": dev["transport"],
                "model": dev.get("model", ""),
            })

        log.info("scan(transport=%s) discovered %d devices", transport, len(discovered))
        return discovered

    def _scan_adb(self) -> list[dict]:
        """Scan for ADB-connected Android devices."""
        devices = []
        try:
            result = subprocess.run(
                ["adb", "devices", "-l"],
                capture_output=True, text=True, timeout=10,
            )
            for line in result.stdout.strip().split("\n")[1:]:
                line = line.strip()
                if not line or line.startswith("*"):
                    continue
                parts = line.split()
                if len(parts) < 2 or parts[1] != "device":
                    continue
                serial = parts[0]
                props = {}
                for p in parts[2:]:
                    if ":" in p:
                        k, v = p.split(":", 1)
                        props[k] = v
                model = props.get("model", serial)
                device_id = f"adb-{serial}"
                devices.append({
                    "device_id": device_id,
                    "transport": "usb",
                    "model": model,
                    "firmware": props.get("version", ""),
                    "capabilities": {"adb_serial": serial, **props},
                })
            if devices:
                log.info("ADB scan found %d device(s)", len(devices))
        except FileNotFoundError:
            log.debug("adb not found, skipping ADB scan")
        except Exception as e:
            log.warning("ADB scan error: %s", e)
        return devices

    # Common ports for device identification
    _PROBE_PORTS = {
        22: "ssh", 23: "telnet", 80: "http", 443: "https",
        8080: "http-alt", 8443: "https-alt", 161: "snmp",
    }

    def _probe_host(self, ip: str) -> dict | None:
        """Probe a host on common ports to identify device type."""
        open_ports: dict[int, str] = {}
        banner = ""
        for port, service in self._PROBE_PORTS.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex((ip, port)) == 0:
                    open_ports[port] = service
                    if port == 22 and not banner:
                        try:
                            banner = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                        except (socket.timeout, OSError):
                            pass
                    elif port in (80, 8080) and not banner:
                        try:
                            sock.sendall(f"HEAD / HTTP/1.0\r\nHost: {ip}\r\n\r\n".encode())
                            banner = sock.recv(4096).decode("utf-8", errors="ignore").strip()
                        except (socket.timeout, OSError):
                            pass
                sock.close()
            except OSError:
                continue

        if not open_ports:
            return None

        # Identify device type from open ports and banner
        model = "Network Device"
        fw = ""
        bl = banner.lower() if banner else ""
        if 22 in open_ports:
            if "openwrt" in bl:
                model = "OpenWrt Router"
            elif "dropbear" in bl:
                model = "Dropbear SSH Device"
            elif "ssh" in bl:
                model = "SSH Host"
            fw = banner.split("\n")[0][:80] if banner else ""
        if 80 in open_ports or 8080 in open_ports:
            if "lighttpd" in bl:
                model = "OpenWrt Router"
                fw = "lighttpd (OpenWrt)"
            elif "openwrt" in bl and model == "Network Device":
                model = "OpenWrt Router"
            elif "router" in bl:
                model = "Router"
            elif "switch" in bl:
                model = "Network Switch"
            elif model == "Network Device" and (80 in open_ports or 8080 in open_ports):
                model = "HTTP Device"
        if 443 in open_ports and model == "Network Device":
            model = "HTTPS Device"
        if 161 in open_ports:
            if model == "Network Device":
                model = "SNMP Device"
        if 23 in open_ports:
            if model == "Network Device":
                model = "Telnet Device"

        return {
            "model": model,
            "firmware": fw,
            "open_ports": open_ports,
            "banner": banner[:200],
        }

    def _scan_network(self) -> list[dict]:
        """Scan local network for devices: routers, switches, APs, SSH hosts."""
        devices = []
        try:
            result = subprocess.run(
                ["arp", "-a"],
                capture_output=True, text=True, timeout=10,
            )
            hosts: list[tuple[str, str]] = []
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Linux format: hostname (1.2.3.4) at aa:bb:cc:dd:ee:ff [ether] on eth0
                m = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([\w:-]+)', line)
                if m:
                    hosts.append((m.group(1), m.group(2)))
                    continue
                # Windows format:   192.168.0.1       2c-ec-f7-12-d9-77     dynamic
                m = re.search(r'^(\d+\.\d+\.\d+\.\d+)\s+([\w-]{17})\s', line)
                if m:
                    ip, mac = m.group(1), m.group(2)
                    if mac in ("ff-ff-ff-ff-ff-ff", "ff:ff:ff:ff:ff:ff"):
                        continue
                    if ip.startswith("224.") or ip.startswith("239."):
                        continue
                    hosts.append((ip, mac))

            # Probe each host in parallel threads
            found: list[tuple[str, str, dict]] = []
            threads: list[threading.Thread] = []
            lock = threading.Lock()

            def _probe(ip: str, mac: str):
                info = self._probe_host(ip)
                if info:
                    with lock:
                        found.append((ip, mac, info))

            for ip, mac in hosts:
                t = threading.Thread(target=_probe, args=(ip, mac))
                t.start()
                threads.append(t)
            for t in threads:
                t.join(timeout=15)

            for ip, mac, info in found:
                device_id = f"net-{ip.replace('.', '-')}"
                devices.append({
                    "device_id": device_id,
                    "transport": "wifi",
                    "model": info["model"],
                    "firmware": info["firmware"],
                    "capabilities": {
                        "ip": ip, "mac": mac,
                        "open_ports": info["open_ports"],
                        "banner": info["banner"],
                    },
                })

            if devices:
                log.info("Network scan found %d device(s)", len(devices))
            else:
                log.info("Network scan found no devices")
        except FileNotFoundError:
            log.debug("arp not found, skipping network scan")
        except Exception as e:
            log.warning("Network scan error: %s", e)
        return devices

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_device(self, device_id: str) -> dict | None:
        """Get a single discovered device by ID."""
        row = self._conn.execute(
            "SELECT * FROM discovered_devices WHERE device_id = ?",
            (device_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["capabilities"] = json.loads(result.get("capabilities", "{}"))
        return result

    def list_devices(self, transport: str | None = None,
                     status: str | None = None) -> list[dict]:
        """List discovered devices with optional filters."""
        query = "SELECT * FROM discovered_devices WHERE 1=1"
        params: list[Any] = []
        if transport is not None:
            query += " AND transport = ?"
            params.append(transport)
        if status is not None:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY discovered_at DESC"

        rows = self._conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["capabilities"] = json.loads(d.get("capabilities", "{}"))
            results.append(d)
        return results

    # ------------------------------------------------------------------
    # Release
    # ------------------------------------------------------------------

    def release(self, device_id: str) -> dict | None:
        """Release a device: set status to 'released'."""
        device = self.get_device(device_id)
        if not device:
            return None

        with self._lock:
            self._conn.execute(
                "UPDATE discovered_devices SET status = 'released' WHERE device_id = ?",
                (device_id,),
            )
            self._conn.commit()

        self._emit("device.released", {"device_id": device_id})
        log.info("released device %s", device_id)

        device["status"] = "released"
        return device

    # ------------------------------------------------------------------
    # Event emission
    # ------------------------------------------------------------------

    def _emit(self, topic: str, payload: dict):
        if self._event_bus:
            from sylion.core.event_bus import SylionEvent
            self._event_bus.publish(SylionEvent(
                event_id="", topic=topic, payload=payload,
                source_module="devices.device_discovery",
            ))


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_var: DeviceDiscoveryService | None = None


def get_device_discovery(db_path=None, event_bus=None):
    global _var
    if _var is None:
        _var = DeviceDiscoveryService(db_path, event_bus)
    return _var
