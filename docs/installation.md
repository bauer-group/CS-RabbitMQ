# Installation

## Prerequisites

- Docker Engine 24+ with the Compose v2 plugin (`docker compose`)
- Python 3.9+ (only for `scripts/generate-env.py`; pure stdlib)
- For Traefik mode: a running Traefik instance on the external `${PROXY_NETWORK}`
  network and DNS records for your hostnames

## 1. Configure environment

```bash
cp .env.example .env          # or:
python scripts/generate-env.py   # creates .env + fills CHANGE_ME_* secrets
```

Edit `.env`:

- `STACK_NAME` — name prefix for containers/volumes/networks
- `RABBITMQ_ADMIN_USER` / `RABBITMQ_ADMIN_PASSWORD` — broker administrator
- `RABBITMQ_ERLANG_COOKIE` — cluster/CLI secret (required even single-node)
- Pick a **sizing preset** (small is the default) — see [sizing-and-tuning.md](sizing-and-tuning.md)
- For Traefik: `CONSOLE_HOSTNAME`, `AMQP_HOSTNAME`, `PROXY_NETWORK`

## 2. (Optional) Define your topology

```bash
cp config/rabbitmq-init.example.json config/rabbitmq-init.json
# edit: vhosts, users, queues, exchanges, bindings, policies
```

Set the credentials your topology references (`APP_PASSWORD`, `MONITORING_PASSWORD`)
in `.env`. See [messaging-topology.md](messaging-topology.md).

> Development mode mounts the **example** topology automatically. For single /
> traefik / coolify, uncomment the `volumes:` mount in the compose file.

## 3. Start

```bash
# Development — local image builds, demo topology
docker compose -f docker-compose.development.yml up -d --build

# Single — pre-built GHCR images, direct host ports
docker compose -f docker-compose.single.yml up -d

# Traefik — HTTPS UI via Let's Encrypt
docker compose -f docker-compose.traefik.yml up -d
#   …with a real LE cert on AMQPS:
docker compose -f docker-compose.traefik.yml --profile tls-letsencrypt up -d
```

## 4. Verify

```bash
# Broker healthy?
docker compose -f docker-compose.development.yml ps

# Init applied the topology? (exits 0)
docker compose -f docker-compose.development.yml logs rabbitmq-init

# Management API
curl -u "$RABBITMQ_ADMIN_USER:$RABBITMQ_ADMIN_PASSWORD" http://localhost:15672/api/overview

# Prometheus metrics
curl http://localhost:15692/metrics | head
```

Open the Management UI at `http://localhost:15672` (or `https://${CONSOLE_HOSTNAME}`).

## Re-running provisioning

The init container is **idempotent** — re-run it any time after editing your
topology JSON:

```bash
docker compose -f docker-compose.development.yml up -d rabbitmq-init
```

Existing resources are updated in place; nothing is deleted (additive only).

## Upgrading RabbitMQ

Bump `RABBITMQ_VERSION` (build) or `RABBITMQ_IMAGE_VERSION` (GHCR) in `.env`,
then `docker compose ... up -d`. The data volume persists across restarts
because the node name (`rabbit@${RABBITMQ_NODE_HOSTNAME}`) is stable. Review the
[RabbitMQ upgrade guide](https://www.rabbitmq.com/docs/upgrade) before crossing
minor versions.
