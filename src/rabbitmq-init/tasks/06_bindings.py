"""
Binding Task

Creates bindings via POST /api/bindings/{vhost}/e/{source}/{q|e}/{dest}.

POST is NOT idempotent (it would create duplicate bindings), so this task
GET-lists existing bindings first and only POSTs when no binding with the same
routing_key + arguments already exists.

JSON config example:
{
  "bindings": [
    { "vhost": "applications", "source": "app.events", "destination": "app.notifications",
      "destination_type": "queue", "routing_key": "notify.#" }
  ]
}
"""

from rmq import binding_matches, enc, error_text

TASK_NAME = "Bindings"
TASK_DESCRIPTION = "Bind queues/exchanges to source exchanges (dedup-checked)"
CONFIG_KEY = "bindings"


def run(items, console, *, client, **kwargs) -> dict:
    if not items:
        return {"skipped": True, "message": "No bindings configured"}

    created = 0
    existing_count = 0

    for b in items:
        vhost = b["vhost"]
        source = b["source"]
        dest = b["destination"]
        dest_type = b.get("destination_type", "queue")
        letter = "q" if dest_type == "queue" else "e"
        routing_key = b.get("routing_key", "")
        arguments = b.get("arguments", {})

        path = f"/api/bindings/{enc(vhost)}/e/{enc(source)}/{letter}/{enc(dest)}"

        # Dedup: is an equivalent binding already present?
        listing = client.get(path)
        already = False
        if listing.status_code == 200:
            already = any(binding_matches(eb, routing_key, arguments) for eb in listing.json())

        if already:
            existing_count += 1
            console.print(f"    [dim]Binding exists: {source} -> {dest} (key='{routing_key}')[/]")
            continue

        resp = client.post(path, {"routing_key": routing_key, "arguments": arguments})
        if resp.status_code in (201, 204):
            created += 1
            console.print(f"    [green]Bound: {source} -> {dest} (key='{routing_key}')[/]")
        else:
            console.print(f"    [red]Failed binding {source}->{dest}: {error_text(resp)}[/]")

    return {
        "changed": created > 0,
        "message": f"{len(items)} binding(s) processed ({created} created, {existing_count} existing)",
    }
