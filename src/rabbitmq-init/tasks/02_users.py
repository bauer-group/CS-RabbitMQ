"""
User Task

Creates users via PUT /api/users/{name}. Idempotent (re-applies password/tags).
Passwords are never logged.

Tags: administrator | monitoring | policymaker | management | impersonator | (none)

JSON config example:
{
  "users": [
    { "name": "app", "password": "${APP_PASSWORD}", "tags": ["management"] },
    { "name": "metrics", "password_hash": "<base64-sha256>", "tags": ["monitoring"] }
  ]
}
"""

from rmq import enc, error_text

TASK_NAME = "Users"
TASK_DESCRIPTION = "Create users with tags (password or password_hash)"
CONFIG_KEY = "users"


def run(items, console, *, client, **kwargs) -> dict:
    if not items:
        return {"skipped": True, "message": "No users configured"}

    created = 0
    updated = 0

    for user in items:
        name = user["name"]
        tags = user.get("tags", [])
        tags_str = ",".join(tags) if isinstance(tags, list) else (tags or "")

        body: dict = {"tags": tags_str}
        if "password_hash" in user:
            body["password_hash"] = user["password_hash"]
        else:
            body["password"] = user.get("password", "")

        state, resp = client.put_resource(f"/api/users/{enc(name)}", body)
        if state == "created":
            created += 1
            console.print(f"    [green]Created user: {name} (tags: {tags_str or 'none'})[/]")
        elif state == "updated":
            updated += 1
            console.print(f"    [dim]Updated user: {name} (tags: {tags_str or 'none'})[/]")
        else:
            console.print(f"    [red]Failed user {name}: {error_text(resp)}[/]")

    return {
        "changed": created > 0,
        "message": f"{len(items)} user(s) processed ({created} created, {updated} updated)",
    }
