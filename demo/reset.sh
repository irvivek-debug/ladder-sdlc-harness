#!/usr/bin/env bash
# Put the demo back to its starting state: no proposals, no outputs, replay-safe mode.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f plant_data/ev_pack_eol/st*/proposed.il
rm -rf demo/out && mkdir -p demo/out
echo "reset done. For the stage: export LADDER_MODE=auto (pinned runs replay, anything new goes live) or LADDER_MODE=replay"
