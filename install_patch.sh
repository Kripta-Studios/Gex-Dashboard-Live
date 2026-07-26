#!/usr/bin/env bash
set -euo pipefail

SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="${1:-/home/Option-Greeks-Plotting-Discord-Bot}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="${TARGET}/.king-node-options-standard-backup-${STAMP}"

[[ -d "${TARGET}/.git" ]] || { echo "Not a Git repository: ${TARGET}" >&2; exit 2; }
mkdir -p "${BACKUP}"

files=(
  .env.king-node.example
  docs/KING_NODE_OPTIONS_STANDARD.md
  modules/volatility_indices.py
  services/king_node_service.py
  scripts/check_king_node_health.py
  scripts/check_thetadata_options_standard.py
  scripts/deploy_king_node_vps.sh
  tests/test_volatility_indices.py
  tests/test_king_node_engine.py
  tests/test_king_node_deployment.py
)

for relative in "${files[@]}"; do
  mkdir -p "${TARGET}/$(dirname "${relative}")"
  if [[ -f "${TARGET}/${relative}" ]]; then
    mkdir -p "${BACKUP}/$(dirname "${relative}")"
    cp -a "${TARGET}/${relative}" "${BACKUP}/${relative}"
  fi
  install -m 0644 "${SRC_DIR}/${relative}" "${TARGET}/${relative}"
done
chmod 0755 \
  "${TARGET}/scripts/check_king_node_health.py" \
  "${TARGET}/scripts/check_thetadata_options_standard.py" \
  "${TARGET}/scripts/deploy_king_node_vps.sh"

echo "Installed into ${TARGET}"
echo "Backup of replaced files: ${BACKUP}"
echo "Review: git -C ${TARGET} status --short"
