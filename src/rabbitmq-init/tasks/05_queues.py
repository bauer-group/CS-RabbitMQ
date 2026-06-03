"""
Queue Task

Creates queues via PUT /api/queues/{vhost}/{name}. Idempotent.

Queue type defaults to quorum (HA-ready). The `type` field is mapped to the
`x-queue-type` argument unless already present in `arguments`. Quorum and
stream queues must be durable and non-auto-delete; this is enforced with a
warning if the config conflicts.

JSON config example:
{
  "queues": [
    { "vhost": "applications", "name": "app.notifications", "type": "quorum",
      "arguments": { "x-dead-letter-exchange": "app.dlx", "x-delivery-limit": 5 } },
    { "vhost": "applications", "name": "app.dead-letter", "type": "quorum" }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Queues"
TASK_DESCRIPTION = "Create queues (default type: quorum)"
CONFIG_KEY = "queues"

DEFAULT_QUEUE_TYPE = "quorum"


def run(items, console, *, client, **kwargs) -> dict:
    if not items:
        return {"skipped": True, "message": "No queues configured"}

    created = 0
    updated = 0

    for q in items:
        vhost = q["vhost"]
        name = q["name"]

        arguments = dict(q.get("arguments", {}))
        qtype = q.get("type", DEFAULT_QUEUE_TYPE)
        arguments.setdefault("x-queue-type", qtype)
        effective_type = arguments["x-queue-type"]

        durable = q.get("durable", True)
        auto_delete = q.get("auto_delete", False)
        if effective_type in ("quorum", "stream"):
            if not durable or auto_delete:
                console.print(
                    f"    [yellow]'{name}': {effective_type} queues must be durable & "
                    f"non-auto-delete — forcing[/]"
                )
            durable = True
            auto_delete = False

        body = {
            "durable": durable,
            "auto_delete": auto_delete,
            "arguments": arguments,
        }
        state, resp = client.put_resource(f"/api/queues/{enc(vhost)}/{enc(name)}", body)
        if state == "created":
            created += 1
            console.print(f"    [green]Created queue: {name} ({effective_type}) @ {vhost}[/]")
        elif state == "updated":
            updated += 1
            console.print(f"    [dim]Queue exists: {name} @ {vhost}[/]")
        else:
            console.print(f"    [red]Failed queue {name}@{vhost}: {error_text(resp)}[/]")

    return {
        "changed": created > 0,
        "message": f"{len(items)} queue(s) processed ({created} created, {updated} existing)",
    }
