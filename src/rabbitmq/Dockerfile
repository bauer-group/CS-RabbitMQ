# ===============================================================================
# BAUER GROUP RabbitMQ - Message Broker Container Image
# ===============================================================================
# Thin, professional wrapper around the official rabbitmq:*-management image.
#
# Adds:
#   - Layered TLS provisioning (self-signed / managed Let's Encrypt / BYO)
#   - Env-driven tuning config rendered at boot (no committed-file mutation)
#   - Default plugins: management, prometheus, shovel, federation
#   - Runtime-toggleable MQTT / STOMP (+ Web variants)
#
# Documentation: https://github.com/bauer-group/CS-RabbitMQ
# ===============================================================================

# ---------------------------------------------------------------------------
# Build Arguments
# ---------------------------------------------------------------------------
# Floating tag: tracks the latest RabbitMQ 4.x (major pinned to avoid a breaking
# jump to 5.x). The base-image monitor rebuilds when this tag's digest moves.
ARG RABBITMQ_REPOSITORY=rabbitmq
ARG RABBITMQ_VERSION=4-management

# ---------------------------------------------------------------------------
# Base Image
# ---------------------------------------------------------------------------
FROM ${RABBITMQ_REPOSITORY}:${RABBITMQ_VERSION}

# ---------------------------------------------------------------------------
# Metadata Labels (Legacy)
# ---------------------------------------------------------------------------
LABEL vendor="BAUER GROUP"
LABEL maintainer="Karl Bauer <karl.bauer@bauer-group.com>"

# ---------------------------------------------------------------------------
# OCI Image Spec Labels
# https://github.com/opencontainers/image-spec/blob/main/annotations.md
# ---------------------------------------------------------------------------
LABEL org.opencontainers.image.title="RabbitMQ"
LABEL org.opencontainers.image.description="RabbitMQ Message Broker - BAUER GROUP Edition (TLS, env-driven tuning, IaC provisioning)"
LABEL org.opencontainers.image.vendor="BAUER GROUP"
LABEL org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/bauer-group/CS-RabbitMQ"
LABEL org.opencontainers.image.url="https://github.com/bauer-group/CS-RabbitMQ"
LABEL org.opencontainers.image.documentation="https://github.com/bauer-group/CS-RabbitMQ#readme"
LABEL org.opencontainers.image.version="0.4.3"

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
# openssl      - self-signed certificate generation
# gettext-base - provides `envsubst` for rendering the tuning config
USER root
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends openssl gettext-base; \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Configuration & Plugins
# ---------------------------------------------------------------------------
COPY etc/rabbitmq/enabled_plugins /etc/rabbitmq/enabled_plugins
COPY etc/rabbitmq/conf.d/20-base.conf /etc/rabbitmq/conf.d/20-base.conf
COPY etc/rabbitmq/conf.d/90-tuning.conf.template /etc/rabbitmq/conf.d/90-tuning.conf.template
RUN mkdir -p /etc/rabbitmq/certs \
    && chown -R rabbitmq:rabbitmq /etc/rabbitmq

# ---------------------------------------------------------------------------
# Custom Entrypoint
# ---------------------------------------------------------------------------
COPY docker-entrypoint-custom.sh /usr/local/bin/docker-entrypoint-custom.sh
RUN chmod a+rx /usr/local/bin/docker-entrypoint-custom.sh

# ---------------------------------------------------------------------------
# Tuning Defaults (small instance — overridable via compose .env)
# ---------------------------------------------------------------------------
ENV RABBITMQ_TLS_MODE=selfsigned \
    RABBITMQ_LOG_LEVEL=info \
    RABBITMQ_VM_MEMORY_HIGH_WATERMARK=2GB \
    RABBITMQ_DISK_FREE_LIMIT=2GB \
    RABBITMQ_CHANNEL_MAX=2048 \
    RABBITMQ_FRAME_MAX=131072 \
    RABBITMQ_MAX_MESSAGE_SIZE=268435456 \
    RABBITMQ_HEARTBEAT=60 \
    RABBITMQ_CONSUMER_TIMEOUT=1800000 \
    RABBITMQ_DEFAULT_QUEUE_TYPE=quorum \
    RABBITMQ_SSL_VERIFY=verify_none \
    RABBITMQ_SSL_FAIL_IF_NO_PEER_CERT=false \
    RABBITMQ_ENABLE_MQTT=false \
    RABBITMQ_ENABLE_WEB_MQTT=false \
    RABBITMQ_ENABLE_STOMP=false \
    RABBITMQ_ENABLE_WEB_STOMP=false

# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
# 5672  AMQP 0-9-1 / AMQP 1.0      5671  AMQPS (TLS)
# 15672 Management UI / HTTP API   15692 Prometheus metrics
# 25672 inter-node / CLI (Erlang distribution)
EXPOSE 5671 5672 15672 15692 25672

# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD rabbitmq-diagnostics -q ping || exit 1

# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
ENTRYPOINT ["docker-entrypoint-custom.sh"]
CMD ["rabbitmq-server"]
