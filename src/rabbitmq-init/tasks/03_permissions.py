"""
Permissions Task

Applies standard permissions (configure/write/read regex per user+vhost) and
optional topic permissions. Both via idempotent PUTs.

CONFIG_KEY is None so the task inspects the whole config (it serves two keys);
it reports "skipped" when neither block is present.

JSON config example:
{
  "permissions": [
    { "vhost": "applications", "user": "app", "configure": "^app\\.", "write": "^app\\.", "read": "^app\\." }
  ],
  "topic_permissions": [
    { "vhost": "applications", "user": "app", "exchange": "app.events", "write": "^notify\\.", "read": "^notify\\." }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Permissions"
TASK_DESCRIPTION = "Apply user permissions and topic permissions"
CONFIG_KEY = None


def _apply_permissions(items, console, client) -> int:
    applied = 0
    for perm in items:
        vhost = perm["vhost"]
        user = perm["user"]
        body = {
            "configure": perm.get("configure", ".*"),
            "write": perm.get("write", ".*"),
            "read": perm.get("read", ".*"),
        }
        resp = client.put(f"/api/permissions/{enc(vhost)}/{enc(user)}", body)
        if resp.status_code in (201, 204):
            applied += 1
            console.print(f"    [green]Permissions: {user}@{vhost} "
                          f"(c={body['configure']} w={body['write']} r={body['read']})[/]")
        else:
            console.print(f"    [red]Failed permissions {user}@{vhost}: {error_text(resp)}[/]")
    return applied


def _apply_topic_permissions(items, console, client) -> int:
    applied = 0
    for perm in items:
        vhost = perm["vhost"]
        user = perm["user"]
        body = {
            "exchange": perm.get("exchange", ""),
            "write": perm.get("write", ".*"),
            "read": perm.get("read", ".*"),
        }
        resp = client.put(f"/api/topic-permissions/{enc(vhost)}/{enc(user)}", body)
        if resp.status_code in (201, 204):
            applied += 1
            console.print(f"    [green]Topic perms: {user}@{vhost} exchange={body['exchange']}[/]")
        else:
            console.print(f"    [red]Failed topic perms {user}@{vhost}: {error_text(resp)}[/]")
    return applied


def run(items, console, *, client, config, **kwargs) -> dict:
    perms = config.get("permissions", [])
    topic_perms = config.get("topic_permissions", [])

    if not perms and not topic_perms:
        return {"skipped": True, "message": "No permissions configured"}

    applied = _apply_permissions(perms, console, client)
    applied += _apply_topic_permissions(topic_perms, console, client)

    total = len(perms) + len(topic_perms)
    return {
        "changed": applied > 0,
        "message": f"{total} permission entr(ies) applied",
    }
