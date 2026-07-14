#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if command -v uv >/dev/null 2>&1; then
  uv run python scripts/setup_database.py
else
  python3 scripts/setup_database.py
fi

