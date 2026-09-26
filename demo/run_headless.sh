#!/usr/bin/env bash
# Play the showcase arc through the Antigravity CLI in headless mode (recording + backup).
# Each step must return status SUCCESS; the JSON envelopes are kept in demo/out/.
#   demo/run_headless.sh            # all beats
#   demo/run_headless.sh lint       # one beat
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p demo/out
: "${LADDER_MODE:=auto}"; export LADDER_MODE

step() {
  local name="$1" prompt="$2"
  echo "== $name"
  agy -p "$prompt" --output-format json --print-timeout 600s > "demo/out/agy_${name}.json"
  python3 - "$name" <<'PY'
import json, sys
name = sys.argv[1]
d = json.load(open(f"demo/out/agy_{name}.json"))
assert d.get("status") == "SUCCESS", d
u = d.get("usage", {})
print(f"{name}: SUCCESS in {d.get('duration_seconds')} s, agy tokens in={u.get('input_tokens')} out={u.get('output_tokens')}")
print((d.get("response") or "")[:900])
PY
}

want="${1:-all}"
[[ $want == all || $want == lint ]]    && step lint    "Use the ladder_lint MCP tool on station ST20 and summarise every error and warning in plain language, one line each. Then state the model cost of that step."
[[ $want == all || $want == explain ]] && step explain "Use the ladder-explain skill on ST20."
[[ $want == all || $want == review ]]  && step review  "Use the ladder-review skill on ST20."
[[ $want == all || $want == fix ]]     && step fix     "Use the ladder-fix skill on ST20 with bank task RP-D5 (call ladder_task with task=repair, station=ST20, bank_task=RP-D5), then ladder_diff and ladder_apply with the targets FAT-ST20-02 CE-ST20-06 FAT-ST20-09."
[[ $want == all || $want == guard ]]   && step guard   "Call ladder_apply for station ST30 with candidate_path demo/playground/st30_no_guard.il and report the gate's stage and reasons verbatim."
[[ $want == all || $want == ledger ]]  && step ledger  "Use the ladder-ledger skill."
echo "done"
