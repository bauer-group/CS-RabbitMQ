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
LABEL org.opencontainers.image.version="0.2.0"

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
RUN addgroup -g 1000 init \
    && adduser -u 1000 -G init -h /app -D init \
    && chown -R init:init /app

USER init

# ---------------------------------------------------------------------------
# Entrypoint (tini for proper signal handling)
# ---------------------------------------------------------------------------
ENTRYPOINT ["/sbin/tini", "--", "python", "main.py"]
