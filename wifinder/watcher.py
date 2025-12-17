"""Core presence detection engine."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable

from .config import Config
from .database import Database, Device
from .notifier import NotificationManager
from .scanner import Scanner


@dataclass
class WatcherState:
    """Current state of the watcher."""

    is_running: bool = False
    last_scan: datetime | None = None
    scan_count: int = 0
    online_count: int = 0
    known_count: int = 0


@dataclass
class PresenceChange:
    """A detected presence change."""

    device: Device
    change_type: str  # "arrived", "left", "new"


class Watcher:
    """Watches the network for presence changes."""

    def __init__(
        self,
        config: Config,
        db: Database,
        on_change: Callable[[PresenceChange], None] | None = None,
    ):
        self.config = config
        self.db = db
        self.scanner = Scanner(config.network)
        self.notifier = NotificationManager(config.notify, config.panic)
        self.on_change = on_change
        self.state = WatcherState()

    def scan_once(self, notify: bool = True) -> list[PresenceChange]:
        """Perform a single scan and return any changes detected.
        
        Args:
            notify: Whether to send notifications for changes. 
                    Set to False for initial discovery scan.
        """
        changes: list[PresenceChange] = []

        # Get currently online devices from DB
        previously_online = {d.mac: d for d in self.db.get_online_devices()}

        # Perform scan
        result = self.scanner.scan()
        self.state.last_scan = result.scan_time
        self.state.scan_count += 1

        currently_seen: set[str] = set()

        for device in result.devices:
            currently_seen.add(device.mac)

            # Check if this is a known device
            existing = self.db.get_device(device.mac)

            if existing is None:
                # New device!
                device.first_seen = result.scan_time
                device.is_online = True
                self.db.upsert_device(device)
                self.db.log_event(device.mac, "arrived")

                change = PresenceChange(device=device, change_type="new")
                changes.append(change)
                if notify:
                    self.notifier.notify_new_device(device)

            elif device.mac not in previously_online:
                # Known device came back online
                device.name = existing.name
                device.group = existing.group
                device.first_seen = existing.first_seen
                device.is_online = True
                self.db.upsert_device(device)
                self.db.log_event(device.mac, "arrived")

                change = PresenceChange(device=device, change_type="arrived")
                changes.append(change)
                if notify:
                    self.notifier.notify_arrival(device)

            else:
                # Device still online, just update last_seen
                device.name = existing.name
                device.group = existing.group
                device.first_seen = existing.first_seen
                device.is_online = True
                self.db.upsert_device(device)

        # Check for devices that should be marked as gone (TTL expired)
        ttl = timedelta(seconds=self.config.device_ttl)
        now = datetime.now()
        
        for mac, device in previously_online.items():
            if mac not in currently_seen:
                # Device not seen in this scan - check if TTL expired
                if device.last_seen and (now - device.last_seen) >= ttl:
                    # TTL expired, mark as gone
                    device.is_online = False
                    self.db.upsert_device(device)
                    self.db.log_event(mac, "left")

                    change = PresenceChange(device=device, change_type="left")
                    changes.append(change)
                    if notify:
                        self.notifier.notify_departure(device)
                # else: TTL not expired yet, device stays "online"

        # Update state
        self.state.online_count = len(self.db.get_online_devices())
        self.state.known_count = len(self.db.get_all_devices())

        # Call callback if provided
        if self.on_change:
            for change in changes:
                self.on_change(change)

        return changes

    def get_who_is_home(self) -> list[Device]:
        """Get list of currently online devices with names (for 'who is home?' queries)."""
        online = self.db.get_online_devices()
        # Prioritize devices with names (known people)
        named = [d for d in online if d.name]
        unnamed = [d for d in online if not d.name]
        return named + unnamed

    def get_summary(self) -> str:
        """Get a human-readable summary of who's home."""
        online = self.get_who_is_home()

        if not online:
            return "Nobody's home"

        named = [d for d in online if d.name]
        unnamed_count = len(online) - len(named)

        parts = []
        if named:
            names = ", ".join(d.name for d in named if d.name)
            parts.append(f"Home: {names}")

        if unnamed_count > 0:
            parts.append(f"+ {unnamed_count} other device(s)")

        return "\n".join(parts)
