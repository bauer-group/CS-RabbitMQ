# RabbitMQ Message Broker

Production-ready [RabbitMQ](https://www.rabbitmq.com/) **4** message broker with
declarative JSON-based provisioning (Infrastructure-as-Code), layered TLS,
Prometheus metrics, and full CI/CD automation.

Tracks the floating `4-management` image tag — always the latest RabbitMQ 4.x,
with the major pinned to avoid a breaking jump to 5.x.

A thin, professional wrapper around the official `rabbitmq:*-management` image plus
a Python init sidecar that provisions your entire topology — vhosts, users,
permissions, exchanges, queues, bindings, policies, shovels — from a single JSON file.

## Features

- **Modern broker** — RabbitMQ 4.x (floating `4-management`), **quorum queues by default** (HA-ready;
  classic mirrored queues were removed in 4.0). AMQP 0-9-1 + AMQP 1.0 core.
- **Declarative provisioning (IaC)** — an idempotent init container applies your
  topology from JSON on every start, via the Management HTTP API:
  - **Virtual hosts**, **users** (+ tags), **permissions** & **topic permissions**
  - **Exchanges**, **queues** (quorum/classic/stream), **bindings** (dedup-checked)
  - **Policies**, **operator policies**, **shovel/federation parameters**
  - `${ENV_VAR}` resolution keeps secrets out of config files; additive & idempotent
- **Sizing presets** — small / medium / large tuning, documented as a table in
  `.env.example`, keyed by the real RAM drivers (connections, queues, backlog).
  **Default: small.**
- **Layered TLS** — self-signed (zero-config) → managed Let's Encrypt (certs-dumper
  sidecar) → bring-your-own. AMQPS on 5671; the web UI gets HTTPS via Traefik/Coolify.
- **Plugins** — Management, Prometheus, Shovel, Federation on by default;
  MQTT / STOMP (+ Web variants) shipped and runtime-toggleable via env.
- **Four deployment modes** — development (local build), single (direct ports),
  Traefik (HTTPS + LE), Coolify (dashboard domains).
- **CI/CD automation** — semantic releases, GHCR image builds, base-image
  monitoring, Dependabot auto-merge, SBOMs, Teams + AI issue triage.

## Quick Start

1. **Clone & enter**
   ```bash
   git clone https://github.com/bauer-group/CS-RabbitMQ.git
   cd CS-RabbitMQ
   ```

2. **Generate `.env`** (fills every `CHANGE_ME_*` secret with random hex)
   ```bash
   python scripts/generate-env.py
   ```

3. **Review `.env`** — set at minimum `RABBITMQ_ADMIN_PASSWORD` (done by the
   generator), pick a sizing preset, and set hostnames for Traefik/Coolify.

4. **(Optional) Define your topology** — copy `config/rabbitmq-init.example.json`
   to `config/rabbitmq-init.json` and edit. (Development mounts the example
   automatically.)

5. **Start**
   ```bash
   # Development (local builds, mounts the example topology)
   docker compose -f docker-compose.development.yml up -d --build

   # Single (direct ports, pre-built GHCR images)
   docker compose -f docker-compose.single.yml up -d

   # Traefik (HTTPS UI via Let's Encrypt)
   docker compose -f docker-compose.traefik.yml up -d
   ```

6. **Access**

   | Mode | AMQP | AMQPS | Management UI | Prometheus |
   | --- | --- | --- | --- | --- |
   | Development / Single | `localhost:5672` | `localhost:5671` | `http://localhost:15672` | `http://localhost:15692/metrics` |
   | Traefik | `${AMQP_HOSTNAME}:5672` | `${AMQP_HOSTNAME}:5671` | `https://${CONSOLE_HOSTNAME}` | (internal) |

   Log in with `RABBITMQ_ADMIN_USER` / `RABBITMQ_ADMIN_PASSWORD`. The insecure
   `guest` account is never created (a default user is defined), is restricted to
   loopback by config, and is **actively deleted** by the init container on every
   run — three independent layers.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                       │
│                                                                │
│   ┌────────────────────┐        ┌──────────────────────────┐  │
│   │      rabbitmq       │◄───────│      rabbitmq-init       │  │
│   │  (custom image)     │  HTTP  │      (one-shot)          │  │
│   │                     │  API   │                          │  │
│   │  AMQP   :5672       │        │  Reads /config/init.json │  │
│   │  AMQPS  :5671       │        │  (volume/seed) and PUTs  │  │
│   │  Mgmt   :15672      │        │  vhosts/users/queues/    │  │
│   │  Prom   :15692      │        │  exchanges/policies/...  │  │
│   │                     │        │  Idempotent on restart   │  │
│   │  Quorum by default  │        └──────────────────────────┘  │
│   │  Self-signed/LE TLS │                                       │
│   └────────────────────┘   (Traefik profile adds certs-dumper) │
│                                                                │
└──────────────────────────────────────────────────────────────┘
```

## Deployment Modes

| Mode | Compose file | UI exposure | Use for |
| --- | --- | --- | --- |
| **Development** | `docker-compose.development.yml` | host port | local builds & testing (mounts demo topology) |
| **Single** | `docker-compose.single.yml` | host port | simple single-host, GHCR images |
| **Traefik** | `docker-compose.traefik.yml` | Traefik + Let's Encrypt | HTTPS UI, optional LE cert on AMQPS |
| **Coolify** | `docker-compose.coolify.yml` | Coolify dashboard | PaaS-managed domains & TLS |

## Configuration

Everything is driven from `.env`:

- **Sizing** — `RABBITMQ_VM_MEMORY_HIGH_WATERMARK` (absolute; no hard container
  cap by design), `RABBITMQ_DISK_FREE_LIMIT`, `RABBITMQ_CHANNEL_MAX`,
  `RABBITMQ_CONSUMER_TIMEOUT`, … See the preset tables in `.env.example` and
  [docs/sizing-and-tuning.md](docs/sizing-and-tuning.md).
- **TLS** — `RABBITMQ_TLS_MODE` (`selfsigned` | `managed` | `byo`).
  See [docs/tls-and-certificates.md](docs/tls-and-certificates.md).
- **Topology** — `config/rabbitmq-init.json`.
  See [docs/messaging-topology.md](docs/messaging-topology.md).
- **Protocols** — `RABBITMQ_ENABLE_MQTT` / `…_STOMP` (+ Web variants).

The broker image renders its tuning config from these env vars at boot
(`src/rabbitmq/etc/rabbitmq/conf.d/90-tuning.conf.template`) — no committed-file
mutation. See [src/rabbitmq/README.md](src/rabbitmq/README.md).

## Ports

| Port | Purpose |
| --- | --- |
| 5672 | AMQP 0-9-1 / AMQP 1.0 |
| 5671 | AMQPS (AMQP over TLS) |
| 15672 | Management UI / HTTP API |
| 15692 | Prometheus metrics |
| 25672 | inter-node / CLI (Erlang distribution) |
| 1883 / 8883 | MQTT / MQTTS (optional) |
| 61613 | STOMP (optional) |

## Documentation

- [Installation](docs/installation.md)
- [Messaging topology (IaC)](docs/messaging-topology.md)
- [TLS & certificates](docs/tls-and-certificates.md)
- [Sizing & tuning](docs/sizing-and-tuning.md)
- [Clustering (scale-out path)](docs/clustering.md)
- [Init container reference](src/rabbitmq-init/README.md)
- [Server image reference](src/rabbitmq/README.md)

## License

MIT License — BAUER GROUP. See [LICENSE](LICENSE).
