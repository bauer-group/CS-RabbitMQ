"""
Limits Task

Applies vhost and user resource limits via idempotent PUTs:
  PUT /api/vhost-limits/{vhost}/{name}   (max-connections, max-queues)
  PUT /api/user-limits/{user}/{name}     (max-connections, max-channels)

These are the guardrails the Management UI exposes under Admin -> Limits; this
task makes them declarative alongside the rest of the topology.

CONFIG_KEY is None (serves two keys); reports "skipped" when both are empty.

JSON config example:
{
  "vhost_limits": [
    { "vhost": "applications", "limits": { "max-connections": 1000, "max-queues": 500 } }
  ],
  "user_limits": [
    { "user": "app", "limits": { "max-connections": 100, "max-channels": 200 } }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Limits"
TASK_DESCRIPTION = "Apply vhost and user resource limits"
CONFIG_KEY = None


def _apply(kind: str, endpoint: str, subject_key: str, items: list, console, client) -> int:
    applied = 0
    for entry in items:
        subject = entry[subject_key]
        limits = entry.get("limits", {})
        if not limits:
            console.print(f"    [yellow]{kind} '{subject}': no limits given, skipped[/]")
            continue
        for name, value in limits.items():
            resp = client.put(f"{endpoint}/{enc(subject)}/{enc(name)}", {"value": value})
            if resp.status_code in (201, 204):
                applied += 1
                console.print(f"    [green]{kind} limit: {subject} {name}={value}[/]")
            else:
                console.print(
                    f"    [red]Failed {kind.lower()} limit {subject} {name}: {error_text(resp)}[/]"
                )
    return applied


def run(items, console, *, client, config, **kwargs) -> dict:
    vhost_limits = config.get("vhost_limits", [])
    user_limits = config.get("user_limits", [])

    if not vhost_limits and not user_limits:
        return {"skipped": True, "message": "No limits configured"}

    applied = _apply("Vhost", "/api/vhost-limits", "vhost", vhost_limits, console, client)
    applied += _apply("User", "/api/user-limits", "user", user_limits, console, client)

    subjects = len(vhost_limits) + len(user_limits)
    return {
        "changed": applied > 0,
        "message": f"{applied} limit(s) applied across {subjects} subject(s)",
    }
