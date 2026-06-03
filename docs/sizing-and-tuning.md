# Sizing & Tuning

The broker is sized entirely from `.env`. Three presets — **small** (default),
**medium**, **large** — are documented as tables in `.env.example` and mapped to
the knobs below. Pick by your steady-state **messages/day** and **concurrent
connections**, then copy that column's values.

## Presets

| Profile | Messages/day | Concurrent conn | `MEM_LIMIT` | `VM_MEMORY_HIGH_WATERMARK` | `DISK_FREE_LIMIT` | `CHANNEL_MAX` | Host RAM |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Small** (default) | < 1 M | < 200 | `2g` | `0.4` | `2GB` | `2048` | 2–4 GB |
| **Medium** | 1 M – 50 M | 200 – 2 000 | `4g` | `0.5` | `4GB` | `4096` | 8 GB |
| **Large** | 50 M – 500 M+ | 2 000 – 10 000+ | `8g` | `0.6` | `8GB` | `8192` | 16–32 GB |

Beyond large on a single node, scale horizontally — see [clustering.md](clustering.md).

## How the knobs work

### Memory (`RABBITMQ_VM_MEMORY_HIGH_WATERMARK` + `RABBITMQ_MEM_LIMIT`)

RabbitMQ 4.x is **cgroup-aware**: it detects the container memory limit set by
`mem_limit`. The watermark is a *fraction* of that limit. When memory use crosses
it, publishers are **throttled** (back-pressure) until consumers catch up.

```
throttle threshold ≈ RABBITMQ_MEM_LIMIT × RABBITMQ_VM_MEMORY_HIGH_WATERMARK
# small: 2g × 0.4 = ~0.8 GB
```

Using a *relative* watermark means the threshold scales automatically when you
raise `mem_limit`. Quorum queues keep their data on disk and only a working set
in memory, so they tolerate this back-pressure gracefully.

### Disk (`RABBITMQ_DISK_FREE_LIMIT`)

A free-disk **floor**. When free space drops below it, the broker blocks
publishers to protect the node. Set it comfortably above your largest expected
backlog. Quorum queues and the message store live under `/var/lib/rabbitmq`
(the `rabbitmq-data` volume).

### Connections & channels (`RABBITMQ_CHANNEL_MAX`)

Channels are cheap but not free (~per-channel memory). `CHANNEL_MAX` caps
channels **per connection** to guard against channel leaks in client apps
(0 = unlimited). Concurrent *connections* are bounded by host file descriptors
and memory rather than a single config key — the per-profile connection figures
above are practical guidance, not a hard cap.

### Consumer timeout (`RABBITMQ_CONSUMER_TIMEOUT`)

Milliseconds a consumer may hold an unacked delivery before RabbitMQ closes its
channel (4.x default `1800000` = 30 min). Raise it for legitimately slow
consumers (long-running jobs); lowering it surfaces stuck consumers faster.

### Heartbeat / frame / message size

- `RABBITMQ_HEARTBEAT` — seconds; detects dead TCP peers (0 disables).
- `RABBITMQ_FRAME_MAX` — max AMQP frame in bytes.
- `RABBITMQ_MAX_MESSAGE_SIZE` — absolute max message in bytes (4.x hard ceiling
  is `536870912` = 512 MiB). Keep large payloads in object storage and send
  references where possible.

## Where the values are applied

The entrypoint renders `/etc/rabbitmq/conf.d/90-tuning.conf` from
`90-tuning.conf.template` via `envsubst` at container start. Inspect the result:

```bash
docker compose exec rabbitmq cat /etc/rabbitmq/conf.d/90-tuning.conf
```

## Verifying under load

```bash
# Live memory / alarms / queue depths
docker compose exec rabbitmq rabbitmq-diagnostics status
docker compose exec rabbitmq rabbitmq-diagnostics memory_breakdown
docker compose exec rabbitmq rabbitmq-diagnostics check_local_alarms
```

Watch the Prometheus endpoint (`:15692/metrics`) — key series:
`rabbitmq_resident_memory_limit_bytes`, `rabbitmq_process_resident_memory_bytes`,
`rabbitmq_disk_space_available_bytes`, `rabbitmq_queue_messages`.
