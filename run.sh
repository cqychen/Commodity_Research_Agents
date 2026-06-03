#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/src"

if [[ "$#" -eq 0 ]]; then
  python -m futures_research_agents.cli --commodity egg --mode full --refresh-market --print-summary
else
  python -m futures_research_agents.cli "$@"
fi
