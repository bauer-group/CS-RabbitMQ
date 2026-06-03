#!/usr/bin/env bash
# =============================================================================
# BAUER GROUP RabbitMQ - Custom Entrypoint
# =============================================================================
# Wraps the official rabbitmq docker-entrypoint.sh with three concerns:
#   1. TLS certificate provisioning (layered: byo / managed / self-signed)
#   2. Env-driven tuning config rendering (90-tuning.conf via envsubst)
#   3. Optional protocol plugin toggles (MQTT / STOMP and their Web variants)
#
# Runs as root so it can write certs/config and chown them; the parent
# entrypoint then drops privileges to the 'rabbitmq' user via gosu.
# =============================================================================
set -euo pipefail

CERT_DIR="/etc/rabbitmq/certs"
CONF_DIR="/etc/rabbitmq/conf.d"
TEMPLATE="${CONF_DIR}/90-tuning.conf.template"
RENDERED="${CONF_DIR}/90-tuning.conf"

# --- Defaults (also declared in the Dockerfile ENV block) --------------------
: "${RABBITMQ_TLS_MODE:=selfsigned}"
: "${RABBITMQ_TLS_CN:=${HOSTNAME}}"
: "${RABBITMQ_TLS_MANAGED_WAIT:=0}"
: "${RABBITMQ_LOG_LEVEL:=info}"
: "${RABBITMQ_VM_MEMORY_HIGH_WATERMARK:=0.4}"
: "${RABBITMQ_DISK_FREE_LIMIT:=2GB}"
: "${RABBITMQ_CHANNEL_MAX:=2048}"
: "${RABBITMQ_FRAME_MAX:=131072}"
: "${RABBITMQ_MAX_MESSAGE_SIZE:=134217728}"
: "${RABBITMQ_HEARTBEAT:=60}"
: "${RABBITMQ_CONSUMER_TIMEOUT:=1800000}"
: "${RABBITMQ_DEFAULT_QUEUE_TYPE:=quorum}"
: "${RABBITMQ_SSL_VERIFY:=verify_none}"
: "${RABBITMQ_SSL_FAIL_IF_NO_PEER_CERT:=false}"
: "${RABBITMQ_ENABLE_MQTT:=false}"
: "${RABBITMQ_ENABLE_WEB_MQTT:=false}"
: "${RABBITMQ_ENABLE_STOMP:=false}"
: "${RABBITMQ_ENABLE_WEB_STOMP:=false}"

log() { printf '%s\n' "$*"; }

banner() {
  log "============================================="
  log " BAUER GROUP RabbitMQ"
  log "============================================="
  log "Hostname            : ${HOSTNAME}"
  log "Timezone            : ${TZ:-Etc/UTC}"
  log "Log level           : ${RABBITMQ_LOG_LEVEL}"
  log "Memory watermark    : ${RABBITMQ_VM_MEMORY_HIGH_WATERMARK} (relative)"
  log "Disk free limit     : ${RABBITMQ_DISK_FREE_LIMIT}"
  log "Default queue type  : ${RABBITMQ_DEFAULT_QUEUE_TYPE}"
  log "TLS mode            : ${RABBITMQ_TLS_MODE}"
  log "Optional protocols  : mqtt=${RABBITMQ_ENABLE_MQTT} web_mqtt=${RABBITMQ_ENABLE_WEB_MQTT} stomp=${RABBITMQ_ENABLE_STOMP} web_stomp=${RABBITMQ_ENABLE_WEB_STOMP}"
  log "============================================="
}

# --- TLS ---------------------------------------------------------------------
generate_self_signed() {
  log "- Generating self-signed TLS certificate (CN=${RABBITMQ_TLS_CN}) -"
  openssl req -nodes -x509 -newkey rsa:4096 \
    -keyout "${CERT_DIR}/key.pem" \
    -out "${CERT_DIR}/cert.pem" \
    -sha256 -days 3650 \
    -subj "/C=DE/ST=BY/L=Cham/O=BAUER GROUP/OU=IT/CN=${RABBITMQ_TLS_CN}/emailAddress=info@bauer-group.com" \
    -addext "subjectAltName=DNS:${RABBITMQ_TLS_CN},DNS:${HOSTNAME},DNS:localhost"
}

provision_tls() {
  mkdir -p "${CERT_DIR}"

  case "${RABBITMQ_TLS_MODE}" in
    byo)
      if [[ ! -f "${CERT_DIR}/cert.pem" || ! -f "${CERT_DIR}/key.pem" ]]; then
        log "ERROR: RABBITMQ_TLS_MODE=byo but ${CERT_DIR}/cert.pem and/or key.pem are missing."
        log "       Bind-mount your certificate and key into ${CERT_DIR}."
        exit 1
      fi
      log "- Using bring-your-own TLS certificate -"
      ;;
    managed)
      # The traefik-certs-dumper sidecar writes cert.pem/key.pem into the
      # shared certs volume. It may not be present on the very first boot.
      local waited=0
      while [[ ! -f "${CERT_DIR}/cert.pem" || ! -f "${CERT_DIR}/key.pem" ]]; do
        if (( waited >= RABBITMQ_TLS_MANAGED_WAIT )); then
          break
        fi
        log "  waiting for managed certificate... (${waited}s/${RABBITMQ_TLS_MANAGED_WAIT}s)"
        sleep 2
        waited=$(( waited + 2 ))
      done
      if [[ -f "${CERT_DIR}/cert.pem" && -f "${CERT_DIR}/key.pem" ]]; then
        log "- Using managed (Let's Encrypt) TLS certificate -"
      else
        log "- Managed certificate not yet available; generating self-signed fallback -"
        generate_self_signed
      fi
      ;;
    selfsigned|*)
      if [[ -f "${CERT_DIR}/cert.pem" && -f "${CERT_DIR}/key.pem" ]]; then
        log "- Existing self-signed TLS certificate found -"
      else
        generate_self_signed
      fi
      ;;
  esac

  # Guarantee a CA file exists. For self-signed certs the cert is its own CA;
  # for managed/byo without an explicit ca.pem, fall back to the cert chain.
  if [[ ! -f "${CERT_DIR}/ca.pem" ]]; then
    cp "${CERT_DIR}/cert.pem" "${CERT_DIR}/ca.pem"
  fi

  chown -R rabbitmq:rabbitmq "${CERT_DIR}"
  chmod 600 "${CERT_DIR}/key.pem"
}

# --- Config rendering --------------------------------------------------------
render_tuning_conf() {
  log "- Rendering ${RENDERED} from template -"
  # Substitute only our known variables so any stray '$' in values is preserved.
  # Single quotes are intentional: envsubst needs the literal ${VAR} names as its
  # substitution allowlist, NOT their expanded values.
  # shellcheck disable=SC2016
  local vars='${RABBITMQ_LOG_LEVEL} ${RABBITMQ_VM_MEMORY_HIGH_WATERMARK} ${RABBITMQ_DISK_FREE_LIMIT} ${RABBITMQ_CHANNEL_MAX} ${RABBITMQ_FRAME_MAX} ${RABBITMQ_MAX_MESSAGE_SIZE} ${RABBITMQ_HEARTBEAT} ${RABBITMQ_CONSUMER_TIMEOUT} ${RABBITMQ_DEFAULT_QUEUE_TYPE} ${RABBITMQ_SSL_VERIFY} ${RABBITMQ_SSL_FAIL_IF_NO_PEER_CERT}'
  envsubst "${vars}" < "${TEMPLATE}" > "${RENDERED}"
  chown rabbitmq:rabbitmq "${RENDERED}"
}

# --- Optional protocol plugins ----------------------------------------------
toggle_plugins() {
  local extra=()
  [[ "${RABBITMQ_ENABLE_MQTT}"     == "true" ]] && extra+=(rabbitmq_mqtt)
  [[ "${RABBITMQ_ENABLE_WEB_MQTT}" == "true" ]] && extra+=(rabbitmq_web_mqtt)
  [[ "${RABBITMQ_ENABLE_STOMP}"    == "true" ]] && extra+=(rabbitmq_stomp)
  [[ "${RABBITMQ_ENABLE_WEB_STOMP}" == "true" ]] && extra+=(rabbitmq_web_stomp)

  if (( ${#extra[@]} > 0 )); then
    log "- Enabling optional protocol plugins: ${extra[*]} -"
    rabbitmq-plugins enable --offline "${extra[@]}"
  fi
}

# --- Hand-off cleanup --------------------------------------------------------
# Our tuning knobs are named after RabbitMQ config keys under the RABBITMQ_
# prefix — which is exactly the official image's DEPRECATED "configure-via-env"
# pattern. The parent entrypoint aborts if it sees them. They have already been
# consumed (rendered into 90-tuning.conf), so strip them before hand-off. The
# image-level vars (DEFAULT_USER/PASS/VHOST, ERLANG_COOKIE, NODENAME) are kept.
unset_render_inputs() {
  unset RABBITMQ_TLS_MODE RABBITMQ_TLS_CN RABBITMQ_TLS_MANAGED_WAIT \
        RABBITMQ_LOG_LEVEL RABBITMQ_VM_MEMORY_HIGH_WATERMARK \
        RABBITMQ_DISK_FREE_LIMIT RABBITMQ_CHANNEL_MAX RABBITMQ_FRAME_MAX \
        RABBITMQ_MAX_MESSAGE_SIZE RABBITMQ_HEARTBEAT RABBITMQ_CONSUMER_TIMEOUT \
        RABBITMQ_DEFAULT_QUEUE_TYPE RABBITMQ_SSL_VERIFY \
        RABBITMQ_SSL_FAIL_IF_NO_PEER_CERT RABBITMQ_ENABLE_MQTT \
        RABBITMQ_ENABLE_WEB_MQTT RABBITMQ_ENABLE_STOMP RABBITMQ_ENABLE_WEB_STOMP
}

# --- Main --------------------------------------------------------------------
banner
provision_tls
render_tuning_conf
toggle_plugins
unset_render_inputs

log "Starting RabbitMQ via parent entrypoint: $*"
exec docker-entrypoint.sh "$@"
