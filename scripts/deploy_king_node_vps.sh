#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/home/Option-Greeks-Plotting-Discord-Bot}"
ENV_FILE="${KING_NODE_ENV_FILE:-/etc/kripta/king-node.env}"
SYSTEMD_DIR="${SYSTEMD_DIR:-/etc/systemd/system}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run as root: sudo APP_DIR=${APP_DIR} bash scripts/deploy_king_node_vps.sh" >&2
    exit 2
fi

required_files=(
    "${APP_DIR}/modules/volatility_indices.py"
    "${APP_DIR}/services/king_node_service.py"
    "${APP_DIR}/services/servidor.py"
    "${APP_DIR}/scripts/check_king_node_health.py"
    "${APP_DIR}/scripts/check_thetadata_options_standard.py"
    "${APP_DIR}/config/king_node_reference.json"
    "${APP_DIR}/systemd/king-node.service"
    "${APP_DIR}/systemd/financial-server.service"
    "${APP_DIR}/.env.king-node.example"
)
for required_file in "${required_files[@]}"; do
    if [[ ! -f "${required_file}" ]]; then
        echo "Missing deployment file: ${required_file}" >&2
        exit 1
    fi
done

install -d -m 0750 "$(dirname "${ENV_FILE}")"
install -d -m 0750 /var/lib/king-node
if [[ ! -f "${ENV_FILE}" ]]; then
    install -m 0600 "${APP_DIR}/.env.king-node.example" "${ENV_FILE}"
    echo "Created ${ENV_FILE}; review it before the next restart."
else
    chmod 0600 "${ENV_FILE}"
    echo "Preserved existing ${ENV_FILE}."
fi

ensure_env_key() {
    local key="$1"
    local value="$2"
    if ! grep -qE "^[[:space:]]*${key}=" "${ENV_FILE}"; then
        printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
        echo "Added ${key} to ${ENV_FILE}."
    fi
}

ensure_env_key KING_NODE_THETA_OPTION_MAX_AGE_SECONDS 180
ensure_env_key KING_NODE_THETA_EXPIRATION_CACHE_SECONDS 21600
ensure_env_key KING_NODE_THETA_MIN_UNDERLYING_OBSERVATIONS 3
ensure_env_key KING_NODE_THETA_MAX_UNDERLYING_DISPERSION_PCT 0.10
ensure_env_key KING_NODE_THETA_MIN_VALID_STRIKES_PER_TERM 8
ensure_env_key KING_NODE_RATE_SYMBOL SOFR
ensure_env_key KING_NODE_RATE_LOOKBACK_DAYS 10
ensure_env_key KING_NODE_RISK_FREE_RATE_PERCENT ""

/usr/bin/python3 -m compileall -q \
    "${APP_DIR}/modules/king_node_engine.py" \
    "${APP_DIR}/modules/volatility_indices.py" \
    "${APP_DIR}/services/king_node_service.py" \
    "${APP_DIR}/services/servidor.py" \
    "${APP_DIR}/scripts/check_king_node_health.py" \
    "${APP_DIR}/scripts/check_thetadata_options_standard.py"

install -m 0644 \
    "${APP_DIR}/systemd/king-node.service" \
    "${SYSTEMD_DIR}/king-node.service"
install -m 0644 \
    "${APP_DIR}/systemd/financial-server.service" \
    "${SYSTEMD_DIR}/financial-server.service"

systemctl daemon-reload
systemctl enable thetadata_feed.service gex_daemon.service
systemctl enable king-node.service financial-server.service

systemctl restart thetadata_feed.service
systemctl restart gex_daemon.service
systemctl restart king-node.service
systemctl restart financial-server.service

for service in \
    thetadata_feed.service \
    gex_daemon.service \
    king-node.service \
    financial-server.service; do
    if ! systemctl is-active --quiet "${service}"; then
        echo "${service} is not active" >&2
        systemctl status "${service}" --no-pager --full || true
        exit 1
    fi
done

echo "KING NODE units installed and active."
echo "Probe Options STANDARD during market hours:"
echo "  sudo -u root /usr/bin/python3 ${APP_DIR}/scripts/check_thetadata_options_standard.py --base-url http://127.0.0.1:25503/v3 --json"
echo "Validate the published snapshot:"
echo "  sudo -u root /usr/bin/python3 ${APP_DIR}/scripts/check_king_node_health.py --snapshot /var/lib/king-node/latest.json"
