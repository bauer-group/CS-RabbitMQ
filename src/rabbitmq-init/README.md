# RabbitMQ Init Container

One-shot initialization container that declaratively configures a RabbitMQ
broker from JSON configuration files via the **Management HTTP API**. Runs on
every start and is fully idempotent.

Pure Python on a `python:3.14-alpine` runtime — no compiled CLI needed, because
the Management API speaks REST and `PUT` is idempotent by contract.

## Configuration loading

Two config files are processed in order:

1. **Built-in default** (`/app/config/default.json`, baked in) — ensures the
   `/` vhost defaults to quorum queues and reinforces full admin permissions
   for `${RABBITMQ_ADMIN_USER}`.
2. **User config** (optional) — read from `/config/init.json` (override with
   `RABBITMQ_INIT_CONFIG`). In development this is a repo bind-mount; in
   production it lives on a named volume and is **seeded** with the baked demo
   (`/app/config/seed.json`) on first boot if absent, then editable at runtime.

Both are processed independently through every task. Idempotency means no
conflict when the same resource appears in both. JSON string values support
`${VAR_NAME}` placeholders, resolved from the environment (missing var → hard
error, so secrets are never silently blanked).

## Security hardening

Before processing any config, the init container **actively deletes the default
`guest` user** (`DELETE /api/users/guest`, idempotent — a 404 just means it was
already gone). This is defense-in-depth: the server image already prevents
`guest` from being created (a default user is defined) and restricts it to
loopback in config, but the init container guarantees it is removed on every run.

## JSON configuration schema

The full configuration file — every block, all fields, types, defaults, allowed
values, and reference tables (queue `arguments`, policy `definition` keys, user
tags) — is documented in the authoritative reference:

> **➡ [docs/messaging-topology.md](../../docs/messaging-topology.md)**

A runnable, annotated example lives at
[`config/rabbitmq-init.example.json`](../../config/rabbitmq-init.example.json)
(mounted automatically in development mode). At a glance, the top level is:

```jsonc
{
  "vhosts": [...], "users": [...], "permissions": [...], "topic_permissions": [...],
  "exchanges": [...], "queues": [...], "bindings": [...],
  "policies": [...], "operator_policies": [...], "parameters": [...], "global_parameters": [...],
  "vhost_limits": [...], "user_limits": [...]
}
```

Every block is optional. String values support `${VAR}` (resolved from the
environment; missing → hard error), and `_`-prefixed keys are treated as comments.

## Task reference

| Order | Task | Config key(s) | Endpoint(s) |
| --- | --- | --- | --- |
| 01 | Virtual Hosts | `vhosts` | `PUT /api/vhosts/{name}` |
| 02 | Users | `users` | `PUT /api/users/{name}` |
| 03 | Permissions | `permissions`, `topic_permissions` | `PUT /api/permissions/...`, `PUT /api/topic-permissions/...` |
| 04 | Exchanges | `exchanges` | `PUT /api/exchanges/{vhost}/{name}` |
| 05 | Queues | `queues` | `PUT /api/queues/{vhost}/{name}` (default `x-queue-type=quorum`) |
| 06 | Bindings | `bindings` | `GET` list → `POST /api/bindings/...` (only if no match) |
| 07 | Policies | `policies`, `operator_policies` | `PUT /api/policies/...`, `PUT /api/operator-policies/...` |
| 08 | Parameters | `parameters`, `global_parameters` | `PUT /api/parameters/...`, `PUT /api/global-parameters/...` |
| 09 | Limits | `vhost_limits`, `user_limits` | `PUT /api/vhost-limits/...`, `PUT /api/user-limits/...` |

> **RabbitMQ 4.x note:** classic mirrored queues (`ha-mode` policies) were removed
> in 4.0. Use **quorum queues** (the default here) or **streams** for HA. The
> init container is **additive** — it creates/updates resources but never deletes;
> remove resources via the management UI or `rabbitmqadmin`.

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `RABBITMQ_MGMT_URL` | `http://rabbitmq:15672` | Management API base URL |
| `RABBITMQ_ADMIN_USER` | `admin` | Admin user (Management API auth) |
| `RABBITMQ_ADMIN_PASSWORD` | *(required)* | Admin password |
| `RABBITMQ_INIT_CONFIG` | `/config/init.json` | Path to user JSON config (volume in prod, bind-mount in dev) |
| `RABBITMQ_WAIT_TIMEOUT` | `120` | Seconds to poll for the Management API (init starts via `service_started` and waits internally) |

Plus any `${VAR}` referenced by your config JSON (e.g. `APP_PASSWORD`).

## Adding a task

1. Drop a numbered file in `tasks/` (e.g. `09_limits.py`).
2. Define `TASK_NAME`, `TASK_DESCRIPTION`, `CONFIG_KEY` (or `None` to read the
   whole config), and `run(items, console, *, client, config, **kwargs) -> dict`.
3. Return `{"changed": bool, "skipped": bool, "message": str}`.

## Tests

```bash
pip install -r requirements-test.txt
pytest            # pure-function unit tests (env resolution, binding match, encoding)
```

## License

MIT License - BAUER GROUP
