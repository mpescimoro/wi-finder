"""Notification system for WiFinder."""

import subprocess
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import httpx

from .config import NotifyConfig, PanicConfig
from .database import Device


class Notifier(ABC):
    """Base class for notifiers."""

    @abstractmethod
    def notify(self, title: str, message: str, device: Device | None = None) -> bool:
        """Send a notification. Returns True if successful."""
        pass


class DesktopNotifier(Notifier):
    """Desktop notifications using system tools."""

    def notify(self, title: str, message: str, device: Device | None = None) -> bool:
        try:
            if sys.platform == "linux":
                subprocess.run(
                    ["notify-send", title, message, "-a", "WiFinder"],
                    check=True,
                    capture_output=True,
                )
            elif sys.platform == "darwin":
                # macOS
                script = f'display notification "{message}" with title "{title}"'
                subprocess.run(
                    ["osascript", "-e", script],
                    check=True,
                    capture_output=True,
                )
            else:
                # Windows - use powershell
                ps_script = f"""
                [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
                $template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
                $template.SelectSingleNode('//text[@id="1"]').InnerText = "{title}"
                $template.SelectSingleNode('//text[@id="2"]').InnerText = "{message}"
                [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("WiFinder").Show($template)
                """
                subprocess.run(
                    ["powershell", "-Command", ps_script],
                    check=True,
                    capture_output=True,
                )
            return True
        except Exception as e:
            print(f"Desktop notification failed: {e}")
            return False


class SoundNotifier(Notifier):
    """Play system beep on events."""

    def notify(self, title: str, message: str, device: Device | None = None) -> bool:
        try:
            if sys.platform == "darwin":
                subprocess.run(["afplay", "/System/Library/Sounds/Glass.aiff"], capture_output=True)
            elif sys.platform != "win32":
                # Linux - try simple beep
                subprocess.run(["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"], 
                             capture_output=True)
            else:
                # Windows
                import winsound
                winsound.MessageBeep()
            return True
        except Exception:
            return False


class TelegramNotifier(Notifier):
    """Send notifications via Telegram bot."""

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{token}"

    def notify(self, title: str, message: str, device: Device | None = None) -> bool:
        try:
            text = f"*{title}*\n{message}"
            if device and device.vendor:
                text += f"\nDevice: {device.vendor}"

            response = httpx.post(
                f"{self.api_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Telegram notification failed: {e}")
            return False

    def get_updates(self) -> list[dict]:
        """Get recent messages (useful for 'who is home?' queries)."""
        try:
            response = httpx.get(
                f"{self.api_url}/getUpdates",
                params={"timeout": 0, "limit": 10},
                timeout=10,
            )
            if response.status_code == 200:
                return response.json().get("result", [])
        except Exception:
            pass
        return []


class WebhookNotifier(Notifier):
    """Send notifications to a webhook URL."""

    def __init__(self, url: str):
        self.url = url

    def notify(self, title: str, message: str, device: Device | None = None) -> bool:
        try:
            payload = {
                "title": title,
                "message": message,
                "timestamp": datetime.now().isoformat(),
            }
            if device:
                payload["device"] = {
                    "mac": device.mac,
                    "name": device.name,
                    "vendor": device.vendor,
                    "ip": device.ip,
                }

            response = httpx.post(self.url, json=payload, timeout=10)
            return 200 <= response.status_code < 300
        except Exception as e:
            print(f"Webhook notification failed: {e}")
            return False


class PanicNotifier:
    """
    The original WiFinder experience.
    
    For when you REALLY need to know someone's coming.
    """

    def __init__(self, message: str = "OHSHITOHSHITOHSHITOHSHITOHSHIT!", sound_loops: int = 1):
        self.message = message
        self.sound_loops = sound_loops

    def panic(self, device: Device | None = None, custom_message: str | None = None) -> None:
        """PANIC! Someone's coming!"""
        msg = custom_message or self.message
        
        # Box banner
        padding = 4
        width = len(msg) + padding * 2
        
        print()
        print("\033[91m┌" + "─" * width + "┐\033[0m")
        print("\033[91m│\033[93m" + msg.center(width) + "\033[91m│\033[0m")
        print("\033[91m└" + "─" * width + "┘\033[0m")
        print()
        
        # Device info
        if device:
            print(f"\033[96m>>> {device.display_name}\033[0m")
            details = []
            if device.vendor:
                details.append(device.vendor)
            if device.ip:
                details.append(device.ip)
            if details:
                print(f"    {' · '.join(details)}")
            print()
        
        # Beep
        for _ in range(self.sound_loops):
            print("\a", end="", flush=True)
            time.sleep(0.2)


# For backwards compatibility with the original script
def ohshit(device: Device | None = None):
    """The classic WiFinder experience."""
    panic = PanicNotifier()
    panic.panic(device)


class NotificationManager:
    """Manages multiple notifiers and handles quiet hours."""

    def __init__(self, config: NotifyConfig, panic_config: PanicConfig | None = None):
        self.config = config
        self.panic_config = panic_config
        self.notifiers: list[Notifier] = []
        self.panic_notifier: PanicNotifier | None = None
        self._setup_notifiers()

    def _setup_notifiers(self) -> None:
        """Set up notifiers based on configuration."""
        if self.config.desktop:
            self.notifiers.append(DesktopNotifier())

        if self.config.sound:
            self.notifiers.append(SoundNotifier())

        if self.config.telegram_token and self.config.telegram_chat_id:
            self.notifiers.append(
                TelegramNotifier(self.config.telegram_token, self.config.telegram_chat_id)
            )

        if self.config.webhook_url:
            self.notifiers.append(WebhookNotifier(self.config.webhook_url))

        # Set up panic notifier if enabled
        if self.panic_config and self.panic_config.enabled:
            self.panic_notifier = PanicNotifier(
                message=self.panic_config.message,
                sound_loops=self.panic_config.sound_loops,
            )

    def _is_quiet_hours(self) -> bool:
        """Check if we're in quiet hours."""
        if self.config.quiet_hours_start is None or self.config.quiet_hours_end is None:
            return False

        current_hour = datetime.now().hour
        start = self.config.quiet_hours_start
        end = self.config.quiet_hours_end

        if start <= end:
            return start <= current_hour < end
        else:
            # Handles overnight quiet hours (e.g., 23:00 to 07:00)
            return current_hour >= start or current_hour < end

    def _should_panic(self, device: Device, is_new: bool) -> bool:
        """Determine if we should trigger panic mode for this device."""
        if not self.panic_notifier or not self.panic_config:
            return False
        
        if self._is_quiet_hours():
            return False
        
        # If only_unknown is set, only panic for devices without names
        if self.panic_config.only_unknown and device.name:
            return False
        
        return True

    def _get_panic_message(self, device: Device) -> str | None:
        """Get custom panic message for device if configured."""
        if not self.panic_config or not self.panic_config.custom_messages:
            return None
        return self.panic_config.custom_messages.get(device.mac.upper())

    def notify_arrival(self, device: Device) -> None:
        """Notify that a device has arrived."""
        if self._is_quiet_hours():
            return

        # Check if we should PANIC
        if self._should_panic(device, is_new=False):
            custom_msg = self._get_panic_message(device)
            self.panic_notifier.panic(device, custom_msg)
            return  # Panic mode overrides normal notifications

        name = device.display_name
        title = "Arrival"
        message = f"{name} is now home"

        for notifier in self.notifiers:
            notifier.notify(title, message, device)

    def notify_departure(self, device: Device) -> None:
        """Notify that a device has left."""
        if self._is_quiet_hours():
            return

        name = device.display_name
        title = "Departure"
        message = f"{name} has left"

        for notifier in self.notifiers:
            notifier.notify(title, message, device)

    def notify_new_device(self, device: Device) -> None:
        """Notify about a new unknown device."""
        if self._is_quiet_hours():
            return

        # Check if we should PANIC
        if self._should_panic(device, is_new=True):
            custom_msg = self._get_panic_message(device)
            self.panic_notifier.panic(device, custom_msg)
            return  # Panic mode overrides normal notifications

        title = "New Device"
        vendor_info = f" ({device.vendor})" if device.vendor else ""
        message = f"Unknown device{vendor_info}\nMAC: {device.mac}"

        for notifier in self.notifiers:
            notifier.notify(title, message, device)
