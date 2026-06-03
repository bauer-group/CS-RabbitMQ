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
2. **User config** (optional) — loaded from `RABBITMQ_INIT_CONFIG` (if set and
   present) or `/app/config/init.json` (fallback, if mounted).

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

```jsonc
{
  "vhosts":     [{ "name": "applications", "default_queue_type": "quorum", "description": "..." }],
  "users":      [{ "name": "app", "password": "${APP_PASSWORD}", "tags": ["management"] }],
  "permissions":[{ "vhost": "applications", "user": "app",
                   "configure": "^app\\.", "write": "^app\\.", "read": "^app\\." }],
  "topic_permissions": [{ "vhost": "applications", "user": "app",
                          "exchange": "app.events", "write": "^notify\\.", "read": "^notify\\." }],
  "exchanges":  [{ "vhost": "applications", "name": "app.events", "type": "topic", "durable": true }],
  "queues":     [{ "vhost": "applications", "name": "app.notifications", "type": "quorum",
                   "arguments": { "x-dead-letter-exchange": "app.dlx", "x-delivery-limit": 5 } }],
  "bindings":   [{ "vhost": "applications", "source": "app.events", "destination": "app.notifications",
                   "destination_type": "queue", "routing_key": "notify.#" }],
  "policies":   [{ "vhost": "applications", "name": "app-dlx", "pattern": "^app\\.",
                   "apply-to": "quorum_queues", "priority": 1,
                   "definition": { "dead-letter-exchange": "app.dlx" } }],
  "operator_policies": [{ "vhost": "applications", "name": "max-len", "pattern": ".*",
                          "apply-to": "queues", "definition": { "max-length": 1000000 } }],
  "parameters": [{ "component": "shovel", "vhost": "applications", "name": "migrate",
                   "value": { "src-uri": "amqp://old", "src-queue": "orders",
                              "dest-uri": "amqp://localhost", "dest-queue": "orders" } }],
  "global_parameters": [{ "name": "cluster_name", "value": "bauer-group-amqp" }]
}
```

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
| `RABBITMQ_INIT_CONFIG` | `/app/config/init.json` | Path to user JSON config |
| `RABBITMQ_WAIT_TIMEOUT` | `60` | Seconds to wait for the Management API |

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
