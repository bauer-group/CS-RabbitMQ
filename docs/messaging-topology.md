# Messaging Topology (Infrastructure-as-Code)

The `rabbitmq-init` container provisions your broker declaratively from JSON on
every start, via the Management HTTP API. It is **idempotent** (safe to re-run)
and **additive** (creates/updates, never deletes).

Two configs are processed in order:

1. **Built-in default** (`src/rabbitmq-init/config/default.json`, baked into the
   image) — ensures `/` defaults to quorum queues and reinforces admin
   permissions.
2. **Your topology** (`config/rabbitmq-init.json`, mounted) — everything else.

`${VAR}` placeholders in string values resolve from the init container's
environment (a missing variable is a hard error, so secrets are never silently
blanked). Pass them through in the compose `rabbitmq-init.environment` block.

## Full schema

```jsonc
{
  "vhosts": [
    { "name": "applications", "default_queue_type": "quorum", "description": "..." }
  ],

  "users": [
    { "name": "${APP_USER}", "password": "${APP_PASSWORD}", "tags": ["management"] }
    // tags: administrator | monitoring | policymaker | management | impersonator | (none)
    // password_hash may be used instead of password
  ],

  "permissions": [
    { "vhost": "applications", "user": "${APP_USER}",
      "configure": "^app\\.", "write": "^app\\.", "read": "^app\\." }
  ],

  "topic_permissions": [
    { "vhost": "applications", "user": "${APP_USER}",
      "exchange": "app.events", "write": "^notify\\.", "read": "^notify\\." }
  ],

  "exchanges": [
    { "vhost": "applications", "name": "app.events", "type": "topic", "durable": true,
      "auto_delete": false, "internal": false, "arguments": {} }
    // type: direct | topic | fanout | headers
  ],

  "queues": [
    { "vhost": "applications", "name": "app.notifications", "type": "quorum",
      "durable": true, "auto_delete": false,
      "arguments": { "x-dead-letter-exchange": "app.dlx", "x-delivery-limit": 5 } }
    // type: quorum (default) | classic | stream
    // quorum/stream are forced durable & non-auto-delete
  ],

  "bindings": [
    { "vhost": "applications", "source": "app.events", "destination": "app.notifications",
      "destination_type": "queue", "routing_key": "notify.#", "arguments": {} }
    // destination_type: queue | exchange
  ],

  "policies": [
    { "vhost": "applications", "name": "app-dlx", "pattern": "^app\\.",
      "apply-to": "quorum_queues", "priority": 1,
      "definition": { "dead-letter-exchange": "app.dlx", "delivery-limit": 5 } }
    // apply-to: all | queues | quorum_queues | classic_queues | streams | exchanges
  ],

  "operator_policies": [
    { "vhost": "applications", "name": "max-len", "pattern": ".*",
      "apply-to": "queues", "definition": { "max-length": 1000000 } }
  ],

  "parameters": [
    { "component": "shovel", "vhost": "applications", "name": "migrate-orders",
      "value": { /* shovel definition, see below */ } }
  ],

  "global_parameters": [
    { "name": "cluster_name", "value": "bauer-group-amqp" }
  ]
}
```

## Field-by-field

| Block | Required keys | Optional keys |
| --- | --- | --- |
| `vhosts` | `name` | `default_queue_type`, `description`, `tags` |
| `users` | `name`, (`password` \| `password_hash`) | `tags` |
| `permissions` | `vhost`, `user` | `configure`, `write`, `read` (default `.*`) |
| `topic_permissions` | `vhost`, `user` | `exchange`, `write`, `read` |
| `exchanges` | `vhost`, `name`, `type` | `durable` (true), `auto_delete`, `internal`, `arguments` |
| `queues` | `vhost`, `name` | `type` (quorum), `durable`, `auto_delete`, `arguments` |
| `bindings` | `vhost`, `source`, `destination` | `destination_type` (queue), `routing_key`, `arguments` |
| `policies` | `vhost`, `name`, `definition` | `pattern` (`.*`), `priority` (0), `apply-to` (all) |
| `parameters` | `component`, `vhost`, `name`, `value` | — |
| `global_parameters` | `name`, `value` | — |

## RabbitMQ 4.x notes

- **Quorum queues are the default.** Classic mirrored queues (`ha-mode` policies)
  were removed in 4.0 — use quorum queues or streams for HA. The init container
  defaults `x-queue-type` to `quorum` and forces durability for quorum/stream.
- **Bindings** are the only non-idempotent verb (the API `POST`s). The init
  container GET-lists existing bindings and only creates one when no binding with
  the same `routing_key` + `arguments` already exists.

## Migrating off the old broker with a Shovel

Dynamic [shovels](https://www.rabbitmq.com/docs/shovel-dynamic) move messages
from a source broker to this one without downtime. Add to `parameters`:

```json
{
  "parameters": [
    {
      "component": "shovel",
      "vhost": "applications",
      "name": "migrate-orders-from-legacy",
      "value": {
        "src-protocol": "amqp091",
        "src-uri": "amqp://USER:PASS@old-broker.example.com:5672",
        "src-queue": "orders",
        "dest-protocol": "amqp091",
        "dest-uri": "amqp://localhost",
        "dest-queue": "orders",
        "ack-mode": "on-confirm",
        "src-delete-after": "never"
      }
    }
  ]
}
```

Keep secrets out of the JSON by using `${VAR}` inside the URI and passing the
value through the init container environment. Once drained, remove the parameter
(deletion is manual — the init container is additive only).
