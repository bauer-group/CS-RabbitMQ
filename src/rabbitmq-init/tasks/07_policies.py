"""
Policies Task

Applies policies and optional operator policies via idempotent PUTs:
  PUT /api/policies/{vhost}/{name}
  PUT /api/operator-policies/{vhost}/{name}

Policies are how RabbitMQ 4.x configures queue behaviour at scale (DLX, TTL,
length limits, delivery-limit, ...). Note: classic-mirror policies (ha-mode)
were removed in 4.0 — use quorum queues for HA instead.

CONFIG_KEY is None (serves two keys); reports "skipped" when both are empty.

JSON config example:
{
  "policies": [
    { "vhost": "applications", "name": "app-dlx", "pattern": "^app\\.",
      "apply-to": "quorum_queues", "priority": 1,
      "definition": { "dead-letter-exchange": "app.dlx", "delivery-limit": 5 } }
  ],
  "operator_policies": [
    { "vhost": "applications", "name": "max-length", "pattern": ".*",
      "apply-to": "queues", "definition": { "max-length": 1000000 } }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Policies"
TASK_DESCRIPTION = "Apply policies and operator policies"
CONFIG_KEY = None


def _apply(kind, endpoint, items, console, client) -> int:
    applied = 0
    for pol in items:
        vhost = pol["vhost"]
        name = pol["name"]
        body = {
            "pattern": pol.get("pattern", ".*"),
            "definition": pol.get("definition", {}),
            "priority": pol.get("priority", 0),
            "apply-to": pol.get("apply-to", "all"),
        }
        resp = client.put(f"{endpoint}/{enc(vhost)}/{enc(name)}", body)
        if resp.status_code in (201, 204):
            applied += 1
            console.print(f"    [green]{kind}: {name} @ {vhost} "
                          f"(pattern='{body['pattern']}', apply-to={body['apply-to']})[/]")
        else:
            console.print(f"    [red]Failed {kind.lower()} {name}@{vhost}: {error_text(resp)}[/]")
    return applied


def run(items, console, *, client, config, **kwargs) -> dict:
    policies = config.get("policies", [])
    operator_policies = config.get("operator_policies", [])

    if not policies and not operator_policies:
        return {"skipped": True, "message": "No policies configured"}

    applied = _apply("Policy", "/api/policies", policies, console, client)
    applied += _apply("Operator policy", "/api/operator-policies", operator_policies, console, client)

    total = len(policies) + len(operator_policies)
    return {
        "changed": applied > 0,
        "message": f"{total} polic(ies) applied",
    }
