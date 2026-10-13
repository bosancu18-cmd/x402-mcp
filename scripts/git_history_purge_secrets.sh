#!/usr/bin/env bash
# Rewrite git history to drop committed secrets. Run ONLY after audit_git_secrets.sh
# finds blobs, and ONLY with operator approval (requires force-push).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v git-filter-repo >/dev/null 2>&1; then
  if python3 -m git_filter_repo --help >/dev/null 2>&1; then
    git_filter_repo() { python3 -m git_filter_repo "$@"; }
  else
    echo "Install git-filter-repo: pip install git-filter-repo" >&2
    exit 1
  fi
fi

echo "Running preflight audit..."
bash "$ROOT/scripts/audit_git_secrets.sh" | tee /tmp/x402-git-audit.txt

if grep -qE '\.keys/|\.env$|\.pem$|id\.json' /tmp/x402-git-audit.txt; then
  echo "Sensitive paths detected — proceeding with filter-repo path drops."
else
  echo "No sensitive blobs found. Skipping history rewrite (nothing to purge)."
  echo "Rotate any keys that ever lived in a local .env regardless."
  exit 0
fi

# Drop only known secret carriers; keep .env.example and ledger/policy.json.
git filter-repo --force \
  --path-glob '.env' \
  --path-glob '.env.local' \
  --path-glob '.env.buyer' \
  --path-glob '**/.env' \
  --path-glob '*.pem' \
  --path-glob '**/*.key' \
  --path-glob '.keys/**' \
  --path-glob '**/id.json' \
  --path-glob '**/*-keypair.json' \
  --path-glob 'secrets/**' \
  --invert-paths

echo "History rewritten. Next steps (operator):"
echo "  1. Rotate EVM_PRIVATE_KEY, SVM_PRIVATE_KEY, CDP_API_KEY_* if any file was ever committed."
echo "  2. git push --force-with-lease origin master  # coordinate with all clones"
echo "  3. Invalidate GitHub tokens / Render env that referenced old keys."
