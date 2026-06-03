#!/usr/bin/env python3
"""
RabbitMQ Init - Declarative Message Broker Provisioning

Reads JSON configuration files and applies them to a RabbitMQ broker via the
Management HTTP API. Designed to be idempotent - safe to run on every
container start (Management API PUTs converge to the declared state).

Configuration loading order:
  1. Built-in default (/app/config/default.json) - always processed
  2. User config - optional, loaded from:
     a) RABBITMQ_INIT_CONFIG env var (if set and file exists)
     b) /app/config/init.json (fallback, if mounted)

JSON values may contain ${ENV_VAR} placeholders for secret injection.
"""

import json
import os
import sys
import time
from importlib import import_module
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from rmq import RabbitMQClient, error_text, resolve_config_values

console = Console()

DEFAULT_CONFIG = "/app/config/default.json"
FALLBACK_USER_CONFIG = "/app/config/init.json"


def get_broker_config() -> dict:
    """Get RabbitMQ connection configuration from environment variables."""
    return {
        "mgmt_url": os.environ.get("RABBITMQ_MGMT_URL", "http://rabbitmq:15672"),
        "user": os.environ.get("RABBITMQ_ADMIN_USER", "admin"),
        "password": os.environ.get("RABBITMQ_ADMIN_PASSWORD", ""),
    }


def harden_security(client: RabbitMQClient) -> None:
    """Actively ensure the default 'guest' user never exists.

    Defense-in-depth alongside RABBITMQ_DEFAULT_USER (prevents creation) and
    loopback_users.guest=true (restricts it to loopback). Idempotent: a 404
    simply means it was already absent. Best-effort — never fails the run.
    """
    try:
        resp = client.delete("/api/users/guest")
    except Exception as e:  # noqa: BLE001
        console.print(f"[yellow]Security: could not check 'guest' user: {e}[/]")
        return

    if resp.status_code in (200, 204):
        console.print("[green]Security: removed default 'guest' user[/]")
    elif resp.status_code == 404:
        console.print("[dim]Security: 'guest' user not present (good)[/]")
    else:
        console.print(f"[yellow]Security: could not remove 'guest': {error_text(resp)}[/]")


def wait_for_rabbitmq(client: RabbitMQClient, timeout: int = 60) -> bool:
    """Wait for the broker Management API to become available and unalarmed."""
    console.print("[dim]Waiting for RabbitMQ Management API...[/]")

    start_time = time.time()
    last_error = "timeout"

    while time.time() - start_time < timeout:
        try:
            # /api/overview confirms the API is up and our credentials are valid.
            resp = client.get("/api/overview")
            if resp.status_code == 200:
                # alarms check returns 200 only when no resource alarm is active.
                client.get("/api/health/checks/alarms")
                console.print("[green]RabbitMQ Management API is ready[/]")
                return True
            if resp.status_code == 401:
                last_error = "authentication failed (check RABBITMQ_ADMIN_USER/PASSWORD)"
                break
            last_error = f"HTTP {resp.status_code}"
        except Exception as e:  # noqa: BLE001 - connection refused while booting
            last_error = str(e)
        time.sleep(2)

    console.print(f"[red]RabbitMQ not ready after {timeout}s: {last_error}[/]")
    return False


def load_config(config_path: str) -> dict | None:
    """Load and resolve a JSON configuration file. Returns None if missing."""
    path = Path(config_path)
    if not path.exists():
        return None
    with open(path) as f:
        raw_config = json.load(f)
    return resolve_config_values(raw_config)


def discover_configs() -> list[tuple[str, dict]]:
    """Discover and load configuration files in order (default, then user)."""
    configs = []

    default = load_config(DEFAULT_CONFIG)
    if default:
        configs.append(("default", default))
    else:
        console.print(f"[yellow]Warning: Built-in default not found: {DEFAULT_CONFIG}[/]")

    user_config_path = os.environ.get("RABBITMQ_INIT_CONFIG", FALLBACK_USER_CONFIG)
    if user_config_path != DEFAULT_CONFIG and Path(user_config_path).exists():
        user_config = load_config(user_config_path)
        if user_config:
            configs.append(("user", user_config))

    return configs


def discover_tasks() -> list:
    """Discover initialization tasks from the tasks/ directory (numbered files)."""
    tasks_dir = Path(__file__).parent / "tasks"
    tasks = []

    for task_file in sorted(tasks_dir.glob("*.py")):
        if task_file.name.startswith("_"):
            continue

        module_name = f"tasks.{task_file.stem}"
        try:
            module = import_module(module_name)
            if hasattr(module, "run"):
                tasks.append({
                    "name": getattr(module, "TASK_NAME", task_file.stem),
                    "description": getattr(module, "TASK_DESCRIPTION", ""),
                    "config_key": getattr(module, "CONFIG_KEY", None),
                    "module": module,
                })
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]Warning: Failed to load task {task_file.name}: {e}[/]")

    return tasks


def process_config(label: str, config: dict, tasks: list, client: RabbitMQClient) -> tuple[int, int, int]:
    """Process a single config through all tasks. Returns (applied, skipped, failed)."""
    applied = 0
    skipped = 0
    failed = 0

    for task in tasks:
        task_name = task["name"]
        config_key = task["config_key"]

        if config_key and not config.get(config_key):
            skipped += 1
            continue

        console.print(f"[bold]> {task_name}[/]")
        if task["description"]:
            console.print(f"  [dim]{task['description']}[/]")

        try:
            items = config.get(config_key, []) if config_key else []
            result = task["module"].run(items, console, client=client, config=config)

            if result.get("skipped"):
                console.print(f"  [dim]Skipped: {result.get('message', 'Not applicable')}[/]")
                skipped += 1
            elif result.get("changed"):
                console.print(f"  [green]+ {result.get('message', 'Done')}[/]")
                applied += 1
            else:
                console.print(f"  [blue]= {result.get('message', 'Already configured')}[/]")
                applied += 1
        except Exception as e:  # noqa: BLE001
            console.print(f"  [red]x Failed: {e}[/]")
            failed += 1

        console.print()

    return applied, skipped, failed


def main() -> int:
    console.print(Panel.fit(
        "[bold blue]RabbitMQ Init[/]\n"
        "[dim]Declarative Message Broker Provisioning[/]",
        border_style="blue",
    ))
    console.print()

    cfg = get_broker_config()
    if not cfg["password"]:
        console.print("[red]Error: RABBITMQ_ADMIN_PASSWORD not set[/]")
        return 1

    console.print(f"[dim]Management API: {cfg['mgmt_url']} (user: {cfg['user']})[/]")
    console.print()

    client = RabbitMQClient(cfg["mgmt_url"], cfg["user"], cfg["password"])

    timeout = int(os.environ.get("RABBITMQ_WAIT_TIMEOUT", "60"))
    if not wait_for_rabbitmq(client, timeout):
        return 1
    console.print()

    # Security hardening before provisioning anything.
    harden_security(client)
    console.print()

    tasks = discover_tasks()
    if not tasks:
        console.print("[yellow]No initialization tasks found[/]")
        return 0

    try:
        configs = discover_configs()
    except (ValueError, json.JSONDecodeError) as e:
        console.print(f"[red]Error loading config: {e}[/]")
        return 1

    if not configs:
        console.print("[yellow]No configuration files found[/]")
        return 0

    total_applied = total_skipped = total_failed = 0

    for label, config in configs:
        console.print(f"[bold cyan]── Processing {label} configuration ──[/]")
        console.print()
        applied, skipped, failed = process_config(label, config, tasks, client)
        total_applied += applied
        total_skipped += skipped
        total_failed += failed

    console.print("─" * 50)
    if total_failed == 0:
        console.print(
            f"[green]Initialization complete "
            f"({total_applied} applied, {total_skipped} skipped)[/]"
        )
        return 0

    console.print(
        f"[red]Initialization had errors "
        f"({total_failed} failed, {total_applied} applied, {total_skipped} skipped)[/]"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
