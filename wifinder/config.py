"""Configuration management for WiFinder."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "wifinder"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"
DEFAULT_DB_FILE = DEFAULT_CONFIG_DIR / "wifinder.db"


@dataclass
class NotifyConfig:
    """Notification settings."""

    sound: bool = True
    desktop: bool = False
    telegram_token: str | None = None
    telegram_chat_id: str | None = None
    webhook_url: str | None = None
    quiet_hours_start: int | None = None  # Hour (0-23)
    quiet_hours_end: int | None = None


@dataclass
class PanicConfig:
    """Panic mode settings - the original WiFinder experience."""

    enabled: bool = False
    message: str = "OHSHITOHSHITOHSHITOHSHITOHSHIT!"
    sound_loops: int = 1
    # Trigger only on unknown devices (not on known family members)
    only_unknown: bool = True
    # Custom messages per device (MAC -> message)
    custom_messages: dict[str, str] | None = None


@dataclass
class Config:
    """Main configuration."""

    network: str = "192.168.1.0/24"
    interval: int = 30  # seconds between scans
    device_ttl: int = 180  # seconds before marking device as gone (3 min default)
    notify: NotifyConfig = field(default_factory=NotifyConfig)
    panic: PanicConfig = field(default_factory=PanicConfig)
    web_port: int = 8080
    web_host: str = "0.0.0.0"
    db_path: Path = DEFAULT_DB_FILE

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_FILE) -> "Config":
        """Load configuration from YAML file."""
        if not path.exists():
            return cls()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        notify_data = data.pop("notify", {})
        notify = NotifyConfig(**notify_data)

        panic_data = data.pop("panic", {})
        panic = PanicConfig(**panic_data)

        if "db_path" in data:
            data["db_path"] = Path(data["db_path"])

        return cls(notify=notify, panic=panic, **data)

    def save(self, path: Path = DEFAULT_CONFIG_FILE) -> None:
        """Save configuration to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {
            "network": self.network,
            "interval": self.interval,
            "device_ttl": self.device_ttl,
            "web_port": self.web_port,
            "web_host": self.web_host,
            "db_path": str(self.db_path),
            "notify": {
                "sound": self.notify.sound,
                "desktop": self.notify.desktop,
                "telegram_token": self.notify.telegram_token,
                "telegram_chat_id": self.notify.telegram_chat_id,
                "webhook_url": self.notify.webhook_url,
                "quiet_hours_start": self.notify.quiet_hours_start,
                "quiet_hours_end": self.notify.quiet_hours_end,
            },
            "panic": {
                "enabled": self.panic.enabled,
                "message": self.panic.message,
                "sound_loops": self.panic.sound_loops,
                "only_unknown": self.panic.only_unknown,
                "custom_messages": self.panic.custom_messages,
            },
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def get_default_network() -> str:
    """Try to auto-detect the local network range."""
    import socket
    import struct

    try:
        # Get default gateway interface
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()

        # Assume /24 network
        parts = local_ip.split(".")
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    except Exception:
        return "192.168.1.0/24"
