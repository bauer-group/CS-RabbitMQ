# Messaging Topology (Infrastructure-as-Code)

The `rabbitmq-init` container provisions your broker declaratively from JSON on
every start, via the RabbitMQ Management HTTP API. This is the **authoritative
reference** for the configuration file: every block, every field, types,
defaults, and allowed values.

- **Idempotent** — safe to run on every start; re-applying converges to the
  declared state.
- **Additive** — it creates and updates resources but **never deletes** them
  (see [Deletion](#deletion-additive-only)).

## Contents

- [How the config is loaded](#how-the-config-is-loaded)
- [Mounting the config per deployment](#mounting-the-config-per-deployment)
- [Environment-variable resolution (`${VAR}`)](#environment-variable-resolution-var)
- [Comment keys (`_`-prefixed)](#comment-keys-_-prefixed)
- [Top-level structure](#top-level-structure)
- Block reference: [vhosts](#vhosts) · [users](#users) · [permissions](#permissions) ·
  [topic_permissions](#topic_permissions) · [exchanges](#exchanges) · [queues](#queues) ·
  [bindings](#bindings) · [policies](#policies) · [operator_policies](#operator_policies) ·
  [parameters](#parameters) · [global_parameters](#global_parameters)
- Reference tables: [queue arguments](#reference-common-queue-arguments) ·
  [policy definition](#reference-common-policy-definition-keys) · [user tags](#reference-user-tags)
- [Generating a `password_hash`](#generating-a-password_hash)
- [Idempotency & deletion](#idempotency)
- [Verifying provisioning](#verifying-provisioning)
- [Migrating off the old broker with a Shovel](#migrating-off-the-old-broker-with-a-shovel)
- [Troubleshooting](#troubleshooting)

---

## How the config is loaded

Two files are processed in order, each independently through all tasks:

1. **Built-in default** — `src/rabbitmq-init/config/default.json`, baked into the
   image. Ensures the `/` vhost defaults to quorum queues and reinforces full
   admin permissions for `${RABBITMQ_ADMIN_USER}`. Always runs.
2. **Your topology** — mounted at `/app/config/init.json` (optional). Everything
   else lives here.

Tasks run in this fixed order (later tasks can depend on earlier ones, e.g.
bindings need their exchange/queue to exist first):

`vhosts → users → permissions → exchanges → queues → bindings → policies → parameters`

Before any of that, the init container performs **security hardening**: it
deletes the default `guest` user (`DELETE /api/users/guest`, idempotent).

## Mounting the config per deployment

| Deployment | How the config is mounted |
| --- | --- |
| **development** | `config/rabbitmq-init.example.json` is mounted automatically — edit it or point `RABBITMQ_INIT_CONFIG` at your own file. |
| **single / traefik / coolify** | Only the built-in default runs until you add a mount. Copy the example, set `RABBITMQ_INIT_CONFIG`, and uncomment the `volumes:` block in the compose file. |

```bash
cp config/rabbitmq-init.example.json config/rabbitmq-init.json
# edit config/rabbitmq-init.json, then in .env:
#   RABBITMQ_INIT_CONFIG=./config/rabbitmq-init.json
# and uncomment in the compose file:
#   volumes:
#     - ${RABBITMQ_INIT_CONFIG:-./config/rabbitmq-init.json}:/app/config/init.json:ro
```

> ⚠️ Only set `RABBITMQ_INIT_CONFIG` to a path that **exists**. Docker silently
> creates an empty *directory* at a missing bind-mount source, which breaks the
> mount.

## Environment-variable resolution (`${VAR}`)

Any **string value** may contain `${VAR_NAME}` placeholders, resolved from the
init container's environment. A **missing variable is a hard error** — the init
fails loudly rather than provisioning a blank secret.

To use a new variable, reference it in the JSON **and** pass it into the init
container's `environment:` block:

```jsonc
// config/rabbitmq-init.json
{ "users": [ { "name": "${WORKER_USER}", "password": "${WORKER_PASSWORD}", "tags": [] } ] }
```

```yaml
# docker-compose.*.yml  (rabbitmq-init service)
environment:
  - WORKER_USER=${WORKER_USER:-worker}
  - WORKER_PASSWORD=${WORKER_PASSWORD}   # from .env (a CHANGE_ME_* secret)
```

Keep secrets in `.env` (never in the committed JSON). `${VAR}` works anywhere a
string appears, including inside connection URIs for shovels/federation.

## Comment keys (`_`-prefixed)

Any object key starting with `_` is treated as a **comment** — it is ignored by
every task and skipped during `${VAR}` resolution (so it may contain literal
`${...}` examples). Use it to annotate your config:

```jsonc
{
  "_comment": "Topology for the orders service. ${VAR} placeholders pull from env.",
  "queues": [
    { "_note": "DLX wired via the app-dlx policy", "vhost": "applications", "name": "app.orders" }
  ]
}
```

---

## Top-level structure

```jsonc
{
  "vhosts":            [ /* ... */ ],
  "users":             [ /* ... */ ],
  "permissions":       [ /* ... */ ],
  "topic_permissions": [ /* ... */ ],
  "exchanges":         [ /* ... */ ],
  "queues":            [ /* ... */ ],
  "bindings":          [ /* ... */ ],
  "policies":          [ /* ... */ ],
  "operator_policies": [ /* ... */ ],
  "parameters":        [ /* ... */ ],
  "global_parameters": [ /* ... */ ]
}
```

Every block is **optional** — include only what you need. Each is an array of
objects; the per-block tables below define each object's fields.

---

## vhosts

Virtual hosts (logical broker partitions). `PUT /api/vhosts/{name}`.

```json
{ "name": "applications", "default_queue_type": "quorum", "description": "App workloads", "tags": ["production"] }
```

| Field | Type | Required | Default | Allowed / notes |
| --- | --- | --- | --- | --- |
| `name` | string | ✅ | — | Vhost name. `/` is the default vhost. |
| `default_queue_type` | string | — | broker default | `quorum` \| `classic` \| `stream` — applied to queues in this vhost that don't declare a type |
| `description` | string | — | `""` | Free text shown in the UI |
| `tags` | string \| array | — | — | Vhost tags (comma-string or list) |

## users

Broker users. `PUT /api/users/{name}`. **Passwords are never logged.**

```json
{ "name": "${APP_USER}", "password": "${APP_PASSWORD}", "tags": ["management"] }
```

| Field | Type | Required | Default | Allowed / notes |
| --- | --- | --- | --- | --- |
| `name` | string | ✅ | — | Username |
| `password` | string | ✅* | — | Plaintext (use `${VAR}`). *One of `password`/`password_hash` is required — omitting both creates a **passwordless** user. |
| `password_hash` | string | ✅* | — | Pre-hashed password (takes precedence). See [Generating a password_hash](#generating-a-password_hash). |
| `tags` | string \| array | — | `[]` (none) | See [user tags](#reference-user-tags) |

## permissions

Per-vhost resource permissions (regex over resource names).
`PUT /api/permissions/{vhost}/{user}`.

```json
{ "vhost": "applications", "user": "${APP_USER}", "configure": "^app\\.", "write": "^app\\.", "read": "^app\\." }
```

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `vhost` | string | ✅ | — | Target vhost |
| `user` | string | ✅ | — | Target user |
| `configure` | string (regex) | — | `.*` | Names the user may declare/delete. `^$` = none. |
| `write` | string (regex) | — | `.*` | Names the user may publish to / bind from |
| `read` | string (regex) | — | `.*` | Names the user may consume from / bind to |

> A read-only monitoring user: `"configure": "^$", "write": "^$", "read": ".*"`.

## topic_permissions

Fine-grained authorization for **topic exchanges** (per-routing-key).
`PUT /api/topic-permissions/{vhost}/{user}`.

```json
{ "vhost": "applications", "user": "${APP_USER}", "exchange": "app.events", "write": "^notify\\.", "read": "^notify\\." }
```

| Field | Type | Required | Default | Notes |
| --- | --- | --- | --- | --- |
| `vhost` | string | ✅ | — | Target vhost |
| `user` | string | ✅ | — | Target user |
| `exchange` | string | — | `""` | Topic exchange the rule applies to (`""` = all) |
| `write` | string (regex) | — | `.*` | Routing keys the user may publish |
| `read` | string (regex) | — | `.*` | Routing keys the user may subscribe to |

## exchanges

`PUT /api/exchanges/{vhost}/{name}`.

```json
{ "vhost": "applications", "name": "app.events", "type": "topic", "durable": true, "arguments": {} }
```

| Field | Type | Required | Default | Allowed / notes |
| --- | --- | --- | --- | --- |
| `vhost` | string | ✅ | — | Target vhost |
| `name` | string | ✅ | — | Exchange name (the default `""` exchange is skipped) |
| `type` | string | — | `direct` | `direct` \| `topic` \| `fanout` \| `headers` (+ plugin types, e.g. `x-delayed-message`) |
| `durable` | bool | — | `true` | Survives broker restart |
| `auto_delete` | bool | — | `false` | Deleted when the last binding is removed |
| `internal` | bool | — | `false` | Not publishable by clients (exchange-to-exchange only) |
| `arguments` | object | — | `{}` | e.g. `{"alternate-exchange": "app.unrouted"}` |

## queues

`PUT /api/queues/{vhost}/{name}`. **Defaults to quorum** (HA-ready).

```json
{ "vhost": "applications", "name": "app.notifications", "type": "quorum",
  "arguments": { "x-dead-letter-exchange": "app.dlx", "x-delivery-limit": 5 } }
```

| Field | Type | Required | Default | Allowed / notes |
| --- | --- | --- | --- | --- |
| `vhost` | string | ✅ | — | Target vhost |
| `name` | string | ✅ | — | Queue name |
| `type` | string | — | `quorum` | `quorum` \| `classic` \| `stream` → sets `x-queue-type` |
| `durable` | bool | — | `true` | **Forced `true`** for quorum/stream |
| `auto_delete` | bool | — | `false` | **Forced `false`** for quorum/stream |
| `arguments` | object | — | `{}` | `x-*` options — see [queue arguments](#reference-common-queue-arguments). `x-queue-type` is set from `type` if absent. |

## bindings

`GET`-list then `POST /api/bindings/{vhost}/e/{source}/{q\|e}/{dest}`. The only
non-idempotent verb, so the task **dedups**: it creates a binding only when none
with the same `routing_key` + `arguments` already exists.

```json
{ "vhost": "applications", "source": "app.events", "destination": "app.notifications",
  "destination_type": "queue", "routing_key": "notify.#" }
```

| Field | Type | Required | Default | Allowed / notes |
| --- | --- | --- | --- | --- |
| `vhost` | string | ✅ | — | Target vhost |
| `source` | string | ✅ | — | Source **exchange** name |
| `destination` | string | ✅ | — | Destination queue or exchange name |
| `destination_type` | string | — | `queue` | `queue` \| `exchange` |
| `routing_key` | string | — | `""` | Binding key (topic/direct). `""` for fanout. |
| `arguments` | object | — | `{}` | For headers exchanges, e.g. `{"x-match": "all", "type": "report"}` |

## policies

Runtime queue/exchange behaviour matched by name pattern. In RabbitMQ 4.x this
is how you configure DLX, TTL, length limits, etc. `PUT /api/policies/{vhost}/{name}`.

```json
{ "vhost": "applications", "name": "app-dlx", "pattern": "^app\\.", "apply-to": "quorum_queues",
  "priority": 1, "definition": { "dead-letter-exchange": "app.dlx", "delivery-limit": 5 } }
```

| Field | Type | Required | Default | Allowed / notes |
| --- | --- | --- | --- | --- |
| `vhost` | string | ✅ | — | Target vhost |
| `name` | string | ✅ | — | Policy name |
| `definition` | object | ✅ | `{}` | The effect — see [policy definition keys](#reference-common-policy-definition-keys) |
| `pattern` | string (regex) | — | `.*` | Matches queue/exchange names |
| `priority` | int | — | `0` | Higher wins when multiple policies match |
| `apply-to` | string | — | `all` | `all` \| `queues` \| `quorum_queues` \| `classic_queues` \| `streams` \| `exchanges` |

> **Classic mirrored queues (`ha-mode`) were removed in 4.0.** Do not put
> `ha-mode`/`ha-params` in a definition — use quorum queues for HA instead.

## operator_policies

Like policies, but **operator-set** — they impose limits a user's own policy
cannot override (guardrails). Only a subset of definition keys is valid (the
safety limits: `max-length`, `max-length-bytes`, `message-ttl`, `expires`,
`delivery-limit`, …). `PUT /api/operator-policies/{vhost}/{name}`.

```json
{ "vhost": "applications", "name": "app-max-length", "pattern": "^app\\.",
  "apply-to": "queues", "definition": { "max-length": 1000000 } }
```

Fields are identical to [policies](#policies).

## parameters

Component runtime parameters — **dynamic shovels and federation upstreams**.
`PUT /api/parameters/{component}/{vhost}/{name}`.

```json
{ "component": "shovel", "vhost": "applications", "name": "migrate-orders",
  "value": { "src-uri": "amqp://old", "src-queue": "orders", "dest-uri": "amqp://localhost", "dest-queue": "orders" } }
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `component` | string | ✅ | `shovel` \| `federation-upstream` \| `federation-upstream-set` |
| `vhost` | string | ✅ | Target vhost |
| `name` | string | ✅ | Parameter name |
| `value` | object | ✅ | Component-specific — see [Shovel example](#migrating-off-the-old-broker-with-a-shovel) and the [Shovel](https://www.rabbitmq.com/docs/shovel-dynamic) / [Federation](https://www.rabbitmq.com/docs/federation) docs |

## global_parameters

Cluster-wide named values. `PUT /api/global-parameters/{name}`.

```json
{ "name": "cluster_name", "value": "eu-central1-broker" }
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `name` | string | ✅ | e.g. `cluster_name`, `internal_cluster_id` |
| `value` | string \| number \| object | ✅ | Type depends on the parameter |

---

## Reference: common queue `arguments`

Set under a queue's `arguments` (or via a policy `definition`, preferred for
fleet-wide settings). Full list: [Queue & message TTL](https://www.rabbitmq.com/docs/ttl),
[Length limits](https://www.rabbitmq.com/docs/maxlength), [Quorum queues](https://www.rabbitmq.com/docs/quorum-queues).

| Argument | Type | Applies to | Purpose |
| --- | --- | --- | --- |
| `x-queue-type` | string | all | `quorum` \| `classic` \| `stream` (set via `type`) |
| `x-dead-letter-exchange` | string | quorum/classic | Where rejected/expired/over-limit messages go |
| `x-dead-letter-routing-key` | string | quorum/classic | Override routing key on dead-letter |
| `x-message-ttl` | int (ms) | quorum/classic | Per-message time-to-live |
| `x-expires` | int (ms) | quorum/classic | Delete the queue after it is unused this long |
| `x-max-length` | int | quorum/classic | Max ready-message count |
| `x-max-length-bytes` | int | all | Max total bytes (also caps streams) |
| `x-overflow` | string | quorum/classic | `drop-head` \| `reject-publish` \| `reject-publish-dlx` |
| `x-delivery-limit` | int | quorum | Redeliveries before dead-lettering (poison-message guard) |
| `x-single-active-consumer` | bool | quorum/classic | Only one consumer active at a time |
| `x-quorum-initial-group-size` | int | quorum | Replica count at creation |
| `x-max-priority` | int | classic | Enable a priority queue (1–255) |
| `x-max-age` | string | stream | Retention, e.g. `7D`, `12h` |
| `x-stream-max-segment-size-bytes` | int | stream | Segment file size |

## Reference: common policy `definition` keys

The policy-form names (no `x-` prefix). A policy is the **recommended** way to
apply these — it covers many queues by pattern and can be changed without
redeclaring. Full list: [Policies](https://www.rabbitmq.com/docs/parameters#policies).

| Key | Type | Equivalent argument |
| --- | --- | --- |
| `dead-letter-exchange` | string | `x-dead-letter-exchange` |
| `dead-letter-routing-key` | string | `x-dead-letter-routing-key` |
| `message-ttl` | int (ms) | `x-message-ttl` |
| `expires` | int (ms) | `x-expires` |
| `max-length` | int | `x-max-length` |
| `max-length-bytes` | int | `x-max-length-bytes` |
| `overflow` | string | `x-overflow` |
| `delivery-limit` | int | `x-delivery-limit` |
| `consumer-timeout` | int (ms) | per-queue consumer ack timeout |
| `queue-version` | int | classic queue storage version (1 \| 2) |

## Reference: user `tags`

| Tag | Grants |
| --- | --- |
| `administrator` | Full management + all vhosts |
| `monitoring` | Read-only access to all management/monitoring data |
| `policymaker` | Manage policies/parameters in permitted vhosts |
| `management` | Management UI/API for permitted vhosts (no node-wide data) |
| `impersonator` | Publish/consume as other users (rarely needed) |
| *(none / `[]`)* | AMQP access only — no management UI |

---

## Generating a `password_hash`

To keep plaintext passwords out of the environment entirely, store a hash. With
the broker running:

```bash
docker compose exec rabbitmq rabbitmqctl hash_password 'your-password'
# -> prints the base64 hash; use it as "password_hash"
```

```json
{ "users": [ { "name": "app", "password_hash": "k0jbVMNT...base64...", "tags": ["management"] } ] }
```

The hash is salted SHA-256 (the broker's default algorithm) and is safe to
commit relative to a plaintext password — though `${VAR}` + `.env` is simpler
for most cases.

## Idempotency

Every block is safe to re-apply. On re-run the init reports `created` vs
`existing`/`updated` per item and exits 0. Re-run it any time after editing:

```bash
docker compose -f docker-compose.development.yml up -d rabbitmq-init
```

### Deletion (additive-only)

The init container **never deletes**. To remove a resource, delete it via the
Management UI or `rabbitmqctl` / `rabbitmqadmin`, then remove it from the JSON so
it isn't recreated on the next run. Example:

```bash
docker compose exec rabbitmq rabbitmqctl delete_queue --vhost applications app.old
```

## Verifying provisioning

```bash
# Init applied the topology and exited 0?
docker compose logs rabbitmq-init

# Inspect the result
docker compose exec rabbitmq rabbitmqctl list_vhosts
docker compose exec rabbitmq rabbitmqctl list_users
docker compose exec rabbitmq rabbitmqctl list_queues --vhost applications name type
docker compose exec rabbitmq rabbitmqctl list_policies --vhost applications
```

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
        "src-uri": "amqp://${LEGACY_USER}:${LEGACY_PASSWORD}@old-broker.example.com:5672",
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

Use `${VAR}` inside the URI and pass the values through the init container's
environment to keep credentials out of the JSON. Once drained, remove the
parameter (deletion is manual — the init is additive only).

## Troubleshooting

| Symptom (init log) | Cause / fix |
| --- | --- |
| `Environment variable 'X' is not set` | A `${X}` in the JSON has no matching env var. Add it to the init container's `environment:` block. |
| `authentication failed` | `RABBITMQ_ADMIN_USER`/`PASSWORD` don't match the broker. On an existing data volume the admin password is fixed at first boot — rotate with `rabbitmqctl change_password`. |
| `RabbitMQ not ready after 60s` | Broker still booting. Raise `RABBITMQ_WAIT_TIMEOUT`, or the server is unhealthy — check its logs. |
| `IsADirectoryError: /app/config/init.json` | `RABBITMQ_INIT_CONFIG` points at a non-existent file; Docker created a directory. Point it at a real file (or leave it unset). |
| Queue exists but settings differ | Most queue arguments are **immutable after creation** — delete and recreate, or apply mutable settings via a policy. |
