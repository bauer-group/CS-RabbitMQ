# ===============================================================================
# RabbitMQ Init - Declarative Message Broker Provisioning
# ===============================================================================
# One-shot container that configures a RabbitMQ broker from JSON configuration
# via the Management HTTP API.
#
# Features:
#   - Virtual hosts, users, permissions, topic permissions
#   - Exchanges, queues (default quorum), bindings (dedup-checked)
#   - Policies, operator policies, shovel/federation parameters
#   - ${ENV_VAR} resolution in JSON values
#   - Idempotent - safe to run on every start
#
# Documentation: https://github.com/bauer-group/CS-RabbitMQ
# ===============================================================================

FROM python:3.14-alpine

# ---------------------------------------------------------------------------
# Metadata Labels (Legacy)
# ---------------------------------------------------------------------------
LABEL vendor="BAUER GROUP"
LABEL maintainer="Karl Bauer <karl.bauer@bauer-group.com>"

# ---------------------------------------------------------------------------
# OCI Image Spec Labels
# ---------------------------------------------------------------------------
LABEL org.opencontainers.image.title="RabbitMQ Init"
LABEL org.opencontainers.image.description="Declarative RabbitMQ provisioning from JSON via the Management HTTP API"
LABEL org.opencontainers.image.vendor="BAUER GROUP"
LABEL org.opencontainers.image.authors="Karl Bauer <karl.bauer@bauer-group.com>"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.source="https://github.com/bauer-group/CS-RabbitMQ"
LABEL org.opencontainers.image.url="https://github.com/bauer-group/CS-RabbitMQ"
LABEL org.opencontainers.image.documentation="https://github.com/bauer-group/CS-RabbitMQ#readme"
LABEL org.opencontainers.image.version="0.4.7"

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
ENV PYTHONUNBUFFERED=1

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
COPY requirements.txt .
RUN apk add --no-cache tini \
    && pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
WORKDIR /app

COPY main.py rmq.py ./
COPY tasks/ ./tasks/
COPY config/ ./config/

# ---------------------------------------------------------------------------
# Non-root User
# ---------------------------------------------------------------------------
# /config holds the user topology (a mounted named volume in production, a repo
# bind-mount in development). Creating it owned by 'init' means a fresh named
# volume inherits that ownership, so first-boot seeding can write into it.
RUN addgroup -g 1000 init \
    && adduser -u 1000 -G init -h /app -D init \
    && mkdir -p /config \
    && chown -R init:init /app /config

USER init

# ---------------------------------------------------------------------------
# Entrypoint (tini for proper signal handling)
# ---------------------------------------------------------------------------
ENTRYPOINT ["/sbin/tini", "--", "python", "main.py"]
