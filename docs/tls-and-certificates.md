# TLS & Certificates

The broker serves **AMQPS on 5671** and the **Management UI on 15672**. These
are two different trust problems:

- **Management UI** is HTTP — terminate TLS at **Traefik** or **Coolify** with
  Let's Encrypt (the `traefik` / `coolify` compose files do this).
- **AMQPS** is *not* HTTP, so Let's Encrypt's HTTP-01 challenge can't terminate
  at RabbitMQ. The broker terminates TLS itself using a certificate provisioned
  by one of three modes below.

Set the mode with `RABBITMQ_TLS_MODE`.

## Mode: `selfsigned` (default)

Zero-config. On first boot the entrypoint generates a 4096-bit, 10-year
self-signed certificate with the BAUER GROUP subject and a SAN for
`RABBITMQ_TLS_CN` (defaults to `AMQP_HOSTNAME`, else the node hostname). The cert
persists in the `rabbitmq-certs` volume.

```ini
RABBITMQ_TLS_MODE=selfsigned
# AMQP_HOSTNAME=amqp.example.com   # used as cert CN/SAN
RABBITMQ_SSL_VERIFY=verify_none    # clients must trust the self-signed CA
```

Good for internal/private networks. Clients must trust the generated CA
(`/etc/rabbitmq/certs/ca.pem`, == the cert itself).

## Mode: `byo` (bring your own)

Mount your own certificate and key (from a corporate PKI or external ACME
tooling). The entrypoint fails fast if they're absent.

```ini
RABBITMQ_TLS_MODE=byo
```

```yaml
# in the compose service:
volumes:
  - ./certs/cert.pem:/etc/rabbitmq/certs/cert.pem:ro
  - ./certs/key.pem:/etc/rabbitmq/certs/key.pem:ro
  # optional, else cert.pem is reused as CA:
  - ./certs/ca.pem:/etc/rabbitmq/certs/ca.pem:ro
```

## Mode: `managed` (Let's Encrypt via certs-dumper)

Reuse the certificate Traefik already obtained from Let's Encrypt. The optional
`certs-dumper` sidecar watches Traefik's `acme.json` and writes `cert.pem` /
`key.pem` into the shared `rabbitmq-certs` volume; the broker serves them on 5671.

```ini
RABBITMQ_TLS_MODE=managed
RABBITMQ_TLS_MANAGED_WAIT=30          # seconds to wait for the cert on first boot
AMQP_HOSTNAME=amqp.example.com        # must be a cert Traefik serves
TRAEFIK_ACME_FILE=/path/to/acme.json  # bind-mounted read-only
```

```bash
docker compose -f docker-compose.traefik.yml --profile tls-letsencrypt up -d
```

### How it works

```
Traefik (solves ACME, stores in acme.json)
        │
        ▼
certs-dumper  ──writes──▶  rabbitmq-certs volume  (cert.pem, key.pem)
                                   │
                                   ▼
                              rabbitmq  ──serves──▶  AMQPS :5671
```

The sidecar runs (see `docker-compose.traefik.yml`):

```
traefik-certs-dumper file --version v3 --watch \
  --source /traefik/acme.json --dest /output \
  --crt-name cert --crt-ext .pem --key-name key --key-ext .pem
```

### Caveats

- **Flat mode dumps the *default* certificate.** If your `acme.json` holds many
  domains, ensure Traefik serves the `AMQP_HOSTNAME` cert as default — or switch
  to `--domain-subdir` plus a `--post-hook` that copies
  `/output/${AMQP_HOSTNAME}/cert.pem` → `/output/cert.pem` (the post-hook needs a
  shell-capable dumper image).
- **Renewal reload.** RabbitMQ does not auto-reload TLS certs on file change.
  After a renewal, reload with
  `docker compose exec rabbitmq rabbitmqctl eval 'ssl:clear_pem_cache().'`
  or restart the broker. Let's Encrypt renews roughly every 60 days, so this is
  infrequent; automate via a cron/hook if desired.

## Peer verification (mTLS)

By default `RABBITMQ_SSL_VERIFY=verify_none` (client cert optional, not checked)
keeps self-signed deployments friction-free. For mutual TLS:

```ini
RABBITMQ_SSL_VERIFY=verify_peer
RABBITMQ_SSL_FAIL_IF_NO_PEER_CERT=true
```

and provide a real CA at `/etc/rabbitmq/certs/ca.pem` that signs your client
certificates.
