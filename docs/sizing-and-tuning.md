# Sizing & Tuning

The broker is sized entirely from `.env`. Three presets — **small** (default),
**medium**, **large** — are documented as a table in `.env.example` and mapped to
the knobs below. RabbitMQ RAM is driven by **connections, queues, and backlog**
(unconsumed messages) plus message size — *not* by raw throughput. A single node
sustains thousands to tens of thousands of msg/s, so size by those real drivers,
not by a daily message count (and remember: a 1-minute burst can dwarf the 24h
total — peak rate matters more than the average).

## Presets

| Profile | Conns | Queues | Peak backlog | `VM_MEMORY_HIGH_WATERMARK` | `DISK_FREE_LIMIT` | Host RAM |
| --- | --- | --- | --- | --- | --- | --- |
| **Small** (default) | < 200 | < 100 | < 100k msgs | `2GB` | `2GB` | 4 GB |
| **Medium** | 200–2 000 | 100–1k | < 1M msgs | `4GB` | `8GB` | 8–12 GB |
| **Large** | 2k–10k+ | 1k–5k | < 10M msgs | `8GB` | `16GB` | 16–32 GB |

`CHANNEL_MAX` is fixed at `2048` across all sizes — it's a per-connection leak
guard (default 2047), **not** a scaling lever. For 10k+ connections also raise
the host file-descriptor limit (`ulimit -n`). Beyond large on a single node,
scale horizontally — see [clustering.md](clustering.md).

## How the knobs work

### Memory (`RABBITMQ_VM_MEMORY_HIGH_WATERMARK`) — and why there is no `mem_limit`

The watermark is an **absolute** memory threshold. When the broker's memory use
crosses it, publishers are **throttled** (back-pressure) until consumers catch
up — a graceful, application-level guard.

```
vm_memory_high_watermark.absolute = RABBITMQ_VM_MEMORY_HIGH_WATERMARK
# small default: 2GB (~40–50% of the 4 GB host target)
```

**There is deliberately no Docker `mem_limit`.** A hard cgroup cap makes Docker
**OOM-kill (SIGKILL)** the container the instant it crosses the limit — abrupt,
mid-transaction, with no graceful shutdown. That turns a healthy broker handling
a transient spike (a GC pause, quorum log compaction, a burst of large messages)
into a crash. The watermark prevents the spike from happening in the first place
by slowing publishers *before* memory is exhausted, so a hard cap is not just
redundant — it's actively harmful to availability.

Set the watermark **below** the RAM the host actually has free for the broker
(the *Host RAM target* column leaves headroom for the Erlang runtime, OS, and
disk cache). Quorum queues keep their data on disk and only a working set in
memory, so they tolerate this back-pressure gracefully.

> If you *must* run under an external orchestrator that imposes a cgroup limit,
> set the watermark to roughly 60–70% of that limit so RabbitMQ throttles well
> before the OOM killer fires.

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
