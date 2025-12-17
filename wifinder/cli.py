"""Command-line interface for WiFinder."""

import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import Config, DEFAULT_CONFIG_FILE, DEFAULT_DB_FILE, get_default_network
from .database import Database
from .watcher import Watcher, PresenceChange

app = typer.Typer(
    name="wifinder",
    help=f"""Network presence detector.

Config: {DEFAULT_CONFIG_FILE}
Database: {DEFAULT_DB_FILE}""",
    add_completion=False,
)
console = Console()


def get_config(config_path: Path | None = None) -> Config:
    """Load configuration from file or defaults."""
    path = config_path or DEFAULT_CONFIG_FILE
    return Config.load(path)


@app.command()
def watch(
    config_path: Path = typer.Option(None, "--config", "-c"),
    network: str = typer.Option(None, "--network", "-n", help="Network to scan (e.g. 192.168.1.0/24)"),
    interval: int = typer.Option(None, "--interval", "-i"),
    panic: bool = typer.Option(False, "--panic", "-p"),
    silent: bool = typer.Option(False, "--silent", "-s"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run in background"),
):
    """Monitor network continuously."""
    if daemon:
        import subprocess
        import sys
        args = [sys.executable, "-m", "wifinder.cli", "watch"]
        if config_path:
            args.extend(["-c", str(config_path)])
        if network:
            args.extend(["-n", network])
        if interval:
            args.extend(["-i", str(interval)])
        if panic:
            args.append("-p")
        if silent:
            args.append("-s")
        
        if sys.platform == "win32":
            subprocess.Popen(args, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        console.print("[green]✓[/green] Started in background")
        return

    config = get_config(config_path)
    if network:
        config.network = network
    if interval:
        config.interval = interval
    if panic:
        config.panic.enabled = True
        config.panic.only_unknown = False

    db = Database(config.db_path)

    def on_change(change: PresenceChange):
        ts = time.strftime("%H:%M:%S")
        if change.change_type == "new":
            console.print(f"[dim]{ts}[/dim] [yellow]NEW[/yellow] {change.device.display_name}")
        elif change.change_type == "arrived":
            console.print(f"[dim]{ts}[/dim] [green]●[/green] {change.device.display_name}")
        elif change.change_type == "left":
            console.print(f"[dim]{ts}[/dim] [red]○[/red] {change.device.display_name}")

    watcher = Watcher(config, db, on_change=on_change)

    console.print(f"Watching {config.network}")
    if panic:
        console.print("[red]PANIC MODE[/red]")
    if silent:
        console.print("[dim]Silent[/dim]")
    console.print(f"[dim]Scan interval: {config.interval}s[/dim]\n")

    # Initial scan
    watcher.scan_once(notify=False)
    console.print(f"[dim]{watcher.state.online_count} online[/dim]\n")

    try:
        while True:
            time.sleep(config.interval)
            watcher.scan_once(notify=not silent)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped[/dim]")


@app.command()
def scan(
    config_path: Path = typer.Option(None, "--config", "-c"),
    network: str = typer.Option(None, "--network", "-n", help="Network to scan (e.g. 192.168.1.0/24)"),
):
    """Single network scan."""
    config = get_config(config_path)
    if network:
        config.network = network
    db = Database(config.db_path)
    watcher = Watcher(config, db)

    watcher.scan_once(notify=False)
    online = db.get_online_devices()

    if not online:
        console.print("[yellow]No devices found[/yellow]")
        return

    for d in online:
        name = d.name or "[dim]unknown[/dim]"
        console.print(f"[green]●[/green] {name} [dim]({d.mac})[/dim]")

    console.print(f"\n[dim]{len(online)} online[/dim]")


@app.command()
def serve(
    config_path: Path = typer.Option(None, "--config", "-c"),
    network: str = typer.Option(None, "--network", "-n", help="Network to scan (e.g. 192.168.1.0/24)"),
    port: int = typer.Option(None, "--port", "-p"),
    host: str = typer.Option(None, "--host", "-H"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run in background"),
):
    """Start web UI."""
    if daemon:
        import subprocess
        import sys
        args = [sys.executable, "-m", "wifinder.cli", "serve"]
        if config_path:
            args.extend(["-c", str(config_path)])
        if network:
            args.extend(["-n", network])
        if port:
            args.extend(["-p", str(port)])
        if host:
            args.extend(["-H", host])
        
        if sys.platform == "win32":
            subprocess.Popen(args, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW)
        else:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        console.print("[green]✓[/green] Started in background")
        return

    config = get_config(config_path)
    if network:
        config.network = network
    if port:
        config.web_port = port
    if host:
        config.web_host = host

    from .web import create_app
    web_app = create_app(config)

    console.print(f"Web UI: http://{config.web_host}:{config.web_port}")
    console.print(f"[dim]Scanning: {config.network}[/dim]")
    web_app.run(host=config.web_host, port=config.web_port, debug=False)


@app.command(name="list")
def list_devices(
    config_path: Path = typer.Option(None, "--config", "-c"),
    all_devices: bool = typer.Option(False, "--all", "-a"),
):
    """List devices."""
    config = get_config(config_path)
    db = Database(config.db_path)

    devices = db.get_all_devices() if all_devices else db.get_online_devices()
    
    if not devices:
        console.print("[dim]No devices[/dim]")
        return

    table = Table(show_header=False, box=None)
    table.add_column(width=3)
    table.add_column()
    table.add_column(style="cyan")
    table.add_column(style="dim")

    for d in devices:
        status = "[green]●[/green]" if d.is_online else "[dim]○[/dim]"
        name = d.name or "[dim]unknown[/dim]"
        group = d.group or ""
        table.add_row(status, name, group, d.mac)

    console.print(table)
    console.print(f"\n[dim]{len(devices)} devices[/dim]")


@app.command()
def add(
    mac: str = typer.Argument(...),
    name: str = typer.Argument(...),
    group: str = typer.Option(None, "--group", "-g"),
    config_path: Path = typer.Option(None, "--config", "-c"),
):
    """Add/rename device."""
    config = get_config(config_path)
    db = Database(config.db_path)

    mac = mac.upper().replace("-", ":").replace(".", ":")
    db.set_device_name(mac, name)
    
    if group:
        db.set_device_group(mac, group)
        console.print(f"[green]✓[/green] {name} ({group})")
    else:
        console.print(f"[green]✓[/green] {name}")


@app.command()
def log(
    mac: str = typer.Argument(None),
    limit: int = typer.Option(20, "--limit", "-n"),
    config_path: Path = typer.Option(None, "--config", "-c"),
):
    """Show arrival/departure log."""
    config = get_config(config_path)
    db = Database(config.db_path)

    events = db.get_history(mac=mac, limit=limit)

    if not events:
        console.print("[dim]No history[/dim]")
        return

    for e in events:
        ts = e.timestamp.strftime("%H:%M")
        name = e.device_name or e.mac
        color = "green" if e.event_type == "arrived" else "red"
        symbol = "●" if e.event_type == "arrived" else "○"
        console.print(f"[dim]{ts}[/dim] [{color}]{symbol}[/{color}] {name}")


@app.command(name="db-path")
def db_path(config_path: Path = typer.Option(None, "--config", "-c")):
    """Show config and database paths."""
    config = get_config(config_path)
    
    console.print(f"Config:   {config_path or DEFAULT_CONFIG_FILE}")
    console.print(f"Database: {config.db_path}")
    
    if config.db_path.exists():
        size = config.db_path.stat().st_size
        console.print(f"[dim]{size:,} bytes[/dim]")


@app.command(name="db-reset")
def db_reset(
    config_path: Path = typer.Option(None, "--config", "-c"),
    force: bool = typer.Option(False, "--force", "-f"),
):
    """Delete all data."""
    config = get_config(config_path)
    
    if not config.db_path.exists():
        console.print("[yellow]No database[/yellow]")
        return
    
    if not force:
        if not typer.confirm("Delete all data?"):
            raise typer.Abort()
    
    config.db_path.unlink()
    console.print("[green]✓[/green] Reset")


@app.command()
def init(config_path: Path = typer.Option(DEFAULT_CONFIG_FILE, "--config", "-c")):
    """Setup wizard."""
    if config_path.exists():
        if not typer.confirm(f"Overwrite {config_path}?"):
            raise typer.Abort()

    network = get_default_network()
    console.print(f"[dim]Detected:[/dim] {network}")
    
    network = typer.prompt("Network", default=network)
    panic = typer.confirm("Enable panic mode?", default=False)

    config = Config(network=network)
    config.panic.enabled = panic
    
    if panic:
        msg = typer.prompt("Panic message", default="OHSHITOHSHITOHSHIT!")
        config.panic.message = msg
    
    config.save(config_path)
    console.print(f"\n[green]✓[/green] Saved to {config_path}")
    console.print("\n[dim]Try:[/dim] wifinder scan")


@app.command(hidden=True)
def ohshit():
    """The original WiFinder experience."""
    from .notifier import ohshit as do_panic
    from .database import Device
    
    fake_device = Device(
        mac="??:??:??:??:??:??",
        vendor="Unknown Intruder",
        ip="192.168.1.???",
    )
    
    do_panic(fake_device)


if __name__ == "__main__":
    app()
