"""Database management for WiFinder using SQLite."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass
class Device:
    """A network device."""

    mac: str
    name: str | None = None
    vendor: str | None = None
    ip: str | None = None
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    is_online: bool = False
    group: str | None = None  # e.g., "family", "guests", "iot"

    @property
    def display_name(self) -> str:
        """Human-readable name for the device."""
        if self.name:
            return self.name
        if self.vendor:
            return f"{self.vendor} ({self.mac[-8:]})"
        return self.mac


@dataclass
class PresenceEvent:
    """A presence event (arrival or departure)."""

    id: int
    mac: str
    event_type: str  # "arrived" or "left"
    timestamp: datetime
    device_name: str | None = None


class Database:
    """SQLite database for storing devices and presence history."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    mac TEXT PRIMARY KEY,
                    name TEXT,
                    vendor TEXT,
                    ip TEXT,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    is_online BOOLEAN DEFAULT 0,
                    "group" TEXT
                );

                CREATE TABLE IF NOT EXISTS presence_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mac TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (mac) REFERENCES devices(mac)
                );

                CREATE INDEX IF NOT EXISTS idx_history_mac ON presence_history(mac);
                CREATE INDEX IF NOT EXISTS idx_history_timestamp ON presence_history(timestamp);
            """)

    def get_device(self, mac: str) -> Device | None:
        """Get a device by MAC address."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM devices WHERE mac = ?", (mac.upper(),)
            ).fetchone()
            if row:
                return self._row_to_device(row)
        return None

    def get_all_devices(self) -> list[Device]:
        """Get all known devices."""
        with self._connection() as conn:
            rows = conn.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
            return [self._row_to_device(row) for row in rows]

    def get_online_devices(self) -> list[Device]:
        """Get all currently online devices."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM devices WHERE is_online = 1 ORDER BY name, mac"
            ).fetchall()
            return [self._row_to_device(row) for row in rows]

    def upsert_device(self, device: Device) -> None:
        """Insert or update a device."""
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO devices (mac, name, vendor, ip, first_seen, last_seen, is_online, "group")
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(mac) DO UPDATE SET
                    name = COALESCE(excluded.name, devices.name),
                    vendor = COALESCE(excluded.vendor, devices.vendor),
                    ip = excluded.ip,
                    last_seen = excluded.last_seen,
                    is_online = excluded.is_online,
                    "group" = COALESCE(excluded."group", devices."group")
                """,
                (
                    device.mac.upper(),
                    device.name,
                    device.vendor,
                    device.ip,
                    device.first_seen or datetime.now(),
                    device.last_seen or datetime.now(),
                    device.is_online,
                    device.group,
                ),
            )

    def set_device_name(self, mac: str, name: str) -> None:
        """Set a friendly name for a device."""
        with self._connection() as conn:
            conn.execute(
                "UPDATE devices SET name = ? WHERE mac = ?",
                (name, mac.upper()),
            )

    def set_device_group(self, mac: str, group: str) -> None:
        """Set the group for a device."""
        with self._connection() as conn:
            conn.execute(
                'UPDATE devices SET "group" = ? WHERE mac = ?',
                (group, mac.upper()),
            )

    def set_all_offline(self) -> None:
        """Mark all devices as offline."""
        with self._connection() as conn:
            conn.execute("UPDATE devices SET is_online = 0")

    def log_event(self, mac: str, event_type: str) -> None:
        """Log a presence event."""
        with self._connection() as conn:
            conn.execute(
                "INSERT INTO presence_history (mac, event_type, timestamp) VALUES (?, ?, ?)",
                (mac.upper(), event_type, datetime.now()),
            )

    def get_history(
        self,
        mac: str | None = None,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[PresenceEvent]:
        """Get presence history, optionally filtered by device."""
        with self._connection() as conn:
            query = """
                SELECT h.id, h.mac, h.event_type, h.timestamp, d.name as device_name
                FROM presence_history h
                LEFT JOIN devices d ON h.mac = d.mac
                WHERE 1=1
            """
            params: list = []

            if mac:
                query += " AND h.mac = ?"
                params.append(mac.upper())

            if since:
                query += " AND h.timestamp >= ?"
                params.append(since)

            query += " ORDER BY h.timestamp DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [
                PresenceEvent(
                    id=row["id"],
                    mac=row["mac"],
                    event_type=row["event_type"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    device_name=row["device_name"],
                )
                for row in rows
            ]

    def get_device_stats(self, mac: str) -> dict:
        """Get statistics for a device."""
        with self._connection() as conn:
            # Count arrivals today
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            arrivals_today = conn.execute(
                """
                SELECT COUNT(*) FROM presence_history
                WHERE mac = ? AND event_type = 'arrived' AND timestamp >= ?
                """,
                (mac.upper(), today_start),
            ).fetchone()[0]

            # First and last seen
            device = self.get_device(mac)

            return {
                "arrivals_today": arrivals_today,
                "first_seen": device.first_seen if device else None,
                "last_seen": device.last_seen if device else None,
            }

    def _row_to_device(self, row: sqlite3.Row) -> Device:
        """Convert a database row to a Device object."""
        return Device(
            mac=row["mac"],
            name=row["name"],
            vendor=row["vendor"],
            ip=row["ip"],
            first_seen=datetime.fromisoformat(row["first_seen"]) if row["first_seen"] else None,
            last_seen=datetime.fromisoformat(row["last_seen"]) if row["last_seen"] else None,
            is_online=bool(row["is_online"]),
            group=row["group"],
        )
