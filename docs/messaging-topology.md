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
- [Where the config lives, per deployment](#where-the-config-lives-per-deployment)
- [Environment-variable resolution (`${VAR}`)](#environment-variable-resolution-var)
- [Comment keys (`_`-prefixed)](#comment-keys-_-prefixed)
- [Top-level structure](#top-level-structure)
- Block reference: [vhosts](#vhosts) · [users](#users) · [permissions](#permissions) ·
  [topic_permissions](#topic_permissions) · [exchanges](#exchanges) · [queues](#queues) ·
  [bindings](#bindings) · [policies](#policies) · [operator_policies](#operator_policies) ·
  [parameters](#parameters) · [global_parameters](#global_parameters) ·
  [vhost_limits](#vhost_limits) · [user_limits](#user_limits)
- Reference tables: [queue arguments](#reference-common-queue-arguments) ·
  [policy definition](#reference-common-policy-definition-keys) · [user tags](#reference-user-tags)
- [Generating a `password_hash`](#generating-a-password_hash)
- [Idempotency & deletion](#idempotency)
- [Verifying provisioning](#verifying-provisioning)
- [Migrating off the old broker with a Shovel](#migrating-off-the-old-broker-with-a-shovel)
- [Troubleshooting](#troubleshooting)

---

## How the config is loaded

The init applies **your topology** from `/config/init.json`. On a fresh volume
this is **seeded with the demo** on first boot (see below), then editable at
runtime.

> The broker itself already creates the `/` vhost (with the broker-wide
> `default_queue_type`) and grants the admin full permissions on it, so the init
> ships **no** baked default config — there's nothing for it to add. (An optional
> `/app/config/default.json` hook remains for forward flexibility but is empty.)

Tasks run in this fixed order (later tasks can depend on earlier ones, e.g.
bindings need their exchange/queue to exist first):

`vhosts → users → permissions → exchanges → queues → bindings → policies → parameters → limits`

Before any of that, the init container performs **security hardening**: it
deletes the default `guest` user (`DELETE /api/users/guest`, idempotent).

## Where the config lives, per deployment

The init always reads `/config/init.json`. How that file gets there differs:

| Deployment | Source of `/config/init.json` |
| --- | --- |
| **development** | Repo file `config/rabbitmq-init.json` is bind-mounted read-only — edit it in your IDE. Ships as the **demo**. Swap the mount to `config/rabbitmq-init.example.json` to exercise every feature. |
| **single / traefik / coolify** | The **`rabbitmq-config` Docker volume** (not the repo). Empty on first boot → **seeded with the demo**, then editable at runtime. |

### The demo (shipped default)

`config/rabbitmq-init.json` creates a vhost `demo`, a quorum queue `demo`, and a
user `demo` (whose password defaults to the admin password for zero-config
convenience — change it for real workloads). Publish to the default exchange
with routing key `demo` to reach the queue.

### Editing the production config at runtime

The config lives on the `rabbitmq-config` volume, so it survives restarts and can
be changed without touching the repo or rebuilding:

```bash
# inspect / replace the live config
docker cp <INIT_or_SERVER_container>:/config/init.json ./init.json
docker cp ./my-topology.json <INIT_container>:/config/init.json
docker compose up -d rabbitmq-init        # re-apply (idempotent)
```

In **Coolify**, edit `/config/init.json` via the volume's file browser, or
override it with a **Coolify File Mount** to `/config/init.json` (content managed
in the Coolify UI). To start from the full example, copy
`config/rabbitmq-init.example.json` into the volume as `init.json`.

> The seed only runs when `/config/init.json` is **absent**. Provide your own
> file (even `{}`) to suppress the demo.

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
  "global_parameters": [ /* ... */ ],
  "vhost_limits":      [ /* ... */ ],
  "user_limits":       [ /* ... */ ]
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

## vhost_limits

Per-vhost guardrails (Management UI: Admin → Limits).
`PUT /api/vhost-limits/{vhost}/{name}`.

```json
{ "vhost": "applications", "limits": { "max-connections": 1000, "max-queues": 500 } }
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `vhost` | string | ✅ | Target vhost |
| `limits` | object | ✅ | Map of limit name → integer |

Limit names: `max-connections` (cap concurrent connections to the vhost),
`max-queues` (cap total queues in the vhost). `-1` or omitting a name removes
the cap.

## user_limits

Per-user guardrails (Management UI: Admin → Limits).
`PUT /api/user-limits/{user}/{name}`.

```json
{ "user": "${APP_USER}", "limits": { "max-connections": 100, "max-channels": 200 } }
```

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `user` | string | ✅ | Target user |
| `limits` | object | ✅ | Map of limit name → integer |

Limit names: `max-connections` (cap concurrent connections opened by the user),
`max-channels` (cap total channels across the user's connections).

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
| `IsADirectoryError: /config/init.json` | A bind-mount source didn't exist, so Docker created a *directory* at the mount target. Point the mount at a real file (production uses a named volume, which avoids this). |
| Queue exists but settings differ | Most queue arguments are **immutable after creation** — delete and recreate, or apply mutable settings via a policy. |
