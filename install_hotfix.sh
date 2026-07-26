#!/usr/bin/env bash
set -euo pipefail

REPO="${1:-/home/Option-Greeks-Plotting-Discord-Bot}"
PATCH_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${REPO}/.king-node-backups/sofr-hotfix-$(date +%Y%m%d-%H%M%S)"

for rel in \
  services/king_node_service.py \
  scripts/check_king_node_health.py \
  tests/test_volatility_indices.py
do
  src="${PATCH_DIR}/${rel}"
  dst="${REPO}/${rel}"
  mkdir -p "${BACKUP_DIR}/$(dirname "${rel}")" "$(dirname "${dst}")"
  if [[ -f "${dst}" ]]; then
    cp -a "${dst}" "${BACKUP_DIR}/${rel}"
  fi
  install -m 0644 "${src}" "${dst}"
done
chmod +x "${REPO}/scripts/check_king_node_health.py"

echo "Hotfix installed. Backup: ${BACKUP_DIR}"
echo "Run tests, then restart king-node.service."
