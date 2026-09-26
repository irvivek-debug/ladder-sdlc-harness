#!/usr/bin/env bash
# Block commits that carry credentials or session material. Scans tracked + staged files.
set -euo pipefail
cd "$(dirname "$0")/.."
files=$(git ls-files -c -o --exclude-standard | grep -vE '^(\.venv|logs|demo/out)/' || true)
patterns='(-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----|"type": *"service_account"|AIza[0-9A-Za-z_-]{35}|ya29\.[0-9A-Za-z_-]{20,}|sk-ant-[0-9A-Za-z_-]{20,}|ghp_[0-9A-Za-z]{30,}|refresh_token"\s*:)'
hits=$(echo "$files" | xargs -I{} grep -EIl "$patterns" {} 2>/dev/null || true)
if [[ -n "$hits" ]]; then echo "secret-like content found in:"; echo "$hits"; exit 1; fi
bad=$(echo "$files" | grep -E '(\.pem|\.key|credentials\.json|application_default_credentials\.json|\.profile[^/]*/)' || true)
if [[ -n "$bad" ]]; then echo "credential-like files present:"; echo "$bad"; exit 1; fi
echo "secret scan: clean ($(echo "$files" | wc -l | tr -d ' ') files)"
