"""
Parameters Task

Applies component runtime parameters (Shovel, Federation upstreams, ...) and
global parameters via idempotent PUTs:
  PUT /api/parameters/{component}/{vhost}/{name}
  PUT /api/global-parameters/{name}

This is how dynamic shovels and federation upstreams are declared — the prime
tool for migrating queues off the OLD broker without downtime.

CONFIG_KEY is None (serves two keys); reports "skipped" when both are empty.

JSON config example:
{
  "parameters": [
    { "component": "shovel", "vhost": "applications", "name": "migrate-orders",
      "value": {
        "src-uri": "amqp://user:pass@old-broker:5672",
        "src-queue": "orders",
        "dest-uri": "amqp://localhost",
        "dest-queue": "orders"
      } }
  ],
  "global_parameters": [
    { "name": "cluster_name", "value": "bauer-group-amqp" }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Parameters"
TASK_DESCRIPTION = "Apply component parameters (shovel/federation) and global parameters"
CONFIG_KEY = None


def _apply_parameters(items, console, client) -> int:
    applied = 0
    for p in items:
        component = p["component"]
        vhost = p["vhost"]
        name = p["name"]
        body = {
            "component": component,
            "vhost": vhost,
            "name": name,
            "value": p.get("value", {}),
        }
        resp = client.put(f"/api/parameters/{enc(component)}/{enc(vhost)}/{enc(name)}", body)
        if resp.status_code in (201, 204):
            applied += 1
            console.print(f"    [green]Parameter: {component}/{name} @ {vhost}[/]")
        else:
            console.print(f"    [red]Failed parameter {component}/{name}@{vhost}: {error_text(resp)}[/]")
    return applied


def _apply_global_parameters(items, console, client) -> int:
    applied = 0
    for p in items:
        name = p["name"]
        body = {"name": name, "value": p.get("value")}
        resp = client.put(f"/api/global-parameters/{enc(name)}", body)
        if resp.status_code in (201, 204):
            applied += 1
            console.print(f"    [green]Global parameter: {name}[/]")
        else:
            console.print(f"    [red]Failed global parameter {name}: {error_text(resp)}[/]")
    return applied


def run(items, console, *, client, config, **kwargs) -> dict:
    parameters = config.get("parameters", [])
    global_parameters = config.get("global_parameters", [])

    if not parameters and not global_parameters:
        return {"skipped": True, "message": "No parameters configured"}

    applied = _apply_parameters(parameters, console, client)
    applied += _apply_global_parameters(global_parameters, console, client)

    total = len(parameters) + len(global_parameters)
    return {
        "changed": applied > 0,
        "message": f"{total} parameter(s) applied",
    }
