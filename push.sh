#!/usr/bin/env bash
# push.sh — push to GitHub using GIT_ACCESS_TOKEN from .env
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REPO_DIR}/.env"

[[ -f "${ENV_FILE}" ]] && set -a && source "${ENV_FILE}" && set +a

if [[ -z "${GIT_ACCESS_TOKEN:-}" ]]; then
  echo "GIT_ACCESS_TOKEN not set. Add it to .env"
  exit 1
fi

cd "${REPO_DIR}"
git remote set-url origin "https://${GIT_ACCESS_TOKEN}@github.com/Stxle2/cortex-nano.git"
git push "$@"
