#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${REPO_ROOT}"

export PYTHONPATH="${REPO_ROOT}/api/src:${REPO_ROOT}/pipelines/src"

exec python -m mypy --config-file=api/pyproject.toml "$@"
