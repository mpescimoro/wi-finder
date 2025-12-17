"""Network scanner using nmap."""

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime

import nmap

from .database import Device


# On Windows, hide nmap console windows
if sys.platform == "win32":
    _original_popen = subprocess.Popen
    
    class _SilentPopen(_original_popen):
        def __init__(self, *args, **kwargs):
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
            if 'startupinfo' not in kwargs:
                si = subprocess.STARTUPINFO()
                si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                si.wShowWindow = subprocess.SW_HIDE
                kwargs['startupinfo'] = si
            super().__init__(*args, **kwargs)
    
    subprocess.Popen = _SilentPopen


@dataclass
class ScanResult:
    """Result of a network scan."""

    devices: list[Device]
    scan_time: datetime
    duration: float  # seconds


class Scanner:
    """Network scanner using nmap."""

    def __init__(self, network: str = "192.168.1.0/24"):
        self.network = network
        self._nm = nmap.PortScanner()
        self._vendor_lookup = None

    def _get_vendor(self, mac: str) -> str | None:
        """Look up vendor from MAC address."""
        if self._vendor_lookup is None:
            try:
                from mac_vendor_lookup import MacLookup

                self._vendor_lookup = MacLookup()
                # Update database on first use (async would be better)
                try:
                    self._vendor_lookup.update_vendors()
                except Exception:
                    pass  # Use cached data if update fails
            except ImportError:
                return None

        try:
            return self._vendor_lookup.lookup(mac)
        except Exception:
            return None

    def scan(self) -> ScanResult:
        """Perform a network scan and return discovered devices."""
        start_time = datetime.now()

        # -sn: Ping scan (no port scan, faster)
        # We need to run as root for ARP-based detection
        self._nm.scan(hosts=self.network, arguments="-sn")

        devices: list[Device] = []
        scan_time = datetime.now()

        for host in self._nm.all_hosts():
            if self._nm[host].state() == "up":
                # Get MAC address (might not be available for all hosts)
                mac = None
                vendor = None

                if "mac" in self._nm[host]["addresses"]:
                    mac = self._nm[host]["addresses"]["mac"]
                    # nmap sometimes provides vendor info
                    if "vendor" in self._nm[host] and mac in self._nm[host]["vendor"]:
                        vendor = self._nm[host]["vendor"][mac]
                    else:
                        vendor = self._get_vendor(mac)

                # Skip devices without MAC (usually the scanning host itself)
                if not mac:
                    continue

                device = Device(
                    mac=mac.upper(),
                    ip=host,
                    vendor=vendor,
                    last_seen=scan_time,
                    is_online=True,
                )
                devices.append(device)

        duration = (datetime.now() - start_time).total_seconds()

        return ScanResult(
            devices=devices,
            scan_time=scan_time,
            duration=duration,
        )

    def quick_ping(self, ip: str) -> bool:
        """Quick check if a specific IP is reachable."""
        try:
            self._nm.scan(hosts=ip, arguments="-sn -T4")
            return ip in self._nm.all_hosts() and self._nm[ip].state() == "up"
        except Exception:
            return False
