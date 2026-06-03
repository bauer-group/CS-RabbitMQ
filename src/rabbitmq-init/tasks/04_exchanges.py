"""
Exchange Task

Creates exchanges via PUT /api/exchanges/{vhost}/{name}. Idempotent.

JSON config example:
{
  "exchanges": [
    { "vhost": "applications", "name": "app.events", "type": "topic", "durable": true },
    { "vhost": "applications", "name": "app.dlx", "type": "fanout", "durable": true }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Exchanges"
TASK_DESCRIPTION = "Create exchanges (topic/direct/fanout/headers)"
CONFIG_KEY = "exchanges"


def run(items, console, *, client, **kwargs) -> dict:
    if not items:
        return {"skipped": True, "message": "No exchanges configured"}

    created = 0
    updated = 0

    for ex in items:
        vhost = ex["vhost"]
        name = ex["name"]
        if name == "":
            console.print("    [yellow]Skipped: cannot declare the default ('') exchange[/]")
            continue

        body = {
            "type": ex.get("type", "direct"),
            "durable": ex.get("durable", True),
            "auto_delete": ex.get("auto_delete", False),
            "internal": ex.get("internal", False),
            "arguments": ex.get("arguments", {}),
        }
        state, resp = client.put_resource(f"/api/exchanges/{enc(vhost)}/{enc(name)}", body)
        if state == "created":
            created += 1
            console.print(f"    [green]Created exchange: {name} ({body['type']}) @ {vhost}[/]")
        elif state == "updated":
            updated += 1
            console.print(f"    [dim]Exchange exists: {name} @ {vhost}[/]")
        else:
            console.print(f"    [red]Failed exchange {name}@{vhost}: {error_text(resp)}[/]")

    return {
        "changed": created > 0,
        "message": f"{len(items)} exchange(s) processed ({created} created, {updated} existing)",
    }
