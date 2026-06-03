"""
Virtual Host Task

Creates virtual hosts via PUT /api/vhosts/{name}. Idempotent.

JSON config example:
{
  "vhosts": [
    { "name": "applications", "default_queue_type": "quorum", "description": "App workloads" }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Virtual Hosts"
TASK_DESCRIPTION = "Create virtual hosts (optionally with a default queue type)"
CONFIG_KEY = "vhosts"


def run(items, console, *, client, **kwargs) -> dict:
    if not items:
        return {"skipped": True, "message": "No vhosts configured"}

    created = 0
    updated = 0

    for vh in items:
        name = vh["name"]
        body: dict = {}
        if "description" in vh:
            body["description"] = vh["description"]
        if "tags" in vh:
            tags = vh["tags"]
            body["tags"] = ",".join(tags) if isinstance(tags, list) else tags
        if "default_queue_type" in vh:
            body["default_queue_type"] = vh["default_queue_type"]

        state, resp = client.put_resource(f"/api/vhosts/{enc(name)}", body)
        if state == "created":
            created += 1
            console.print(f"    [green]Created vhost: {name}[/]")
        elif state == "updated":
            updated += 1
            console.print(f"    [dim]Vhost exists: {name}[/]")
        else:
            console.print(f"    [red]Failed vhost {name}: {error_text(resp)}[/]")

    return {
        "changed": created > 0,
        "message": f"{len(items)} vhost(s) processed ({created} created, {updated} existing)",
    }
