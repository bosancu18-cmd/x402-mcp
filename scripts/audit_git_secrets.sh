#!/usr/bin/env bash
# Scan the entire git object graph for sensitive filename patterns.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

SENSITIVE_REGEX='(\.env$|\.env\.[^/]+$|\.pem$|id\.json$|\.key$|/\.keys/|wallet\.json$|credentials\.json$)'

echo "== Tracked sensitive paths (should be empty except templates) =="
git log --all --pretty=format: --name-only \
  | grep -E "$SENSITIVE_REGEX" \
  | grep -v '^\.env\.example$' \
  | grep -v '^desktop-admin/\.env\.example$' \
  | grep -v '^dashboard/\.env\.production$' \
  | grep -v '^deployment/seller\.env\.example$' \
  | sort -u || true

echo
echo "== Blob paths matching sensitive patterns =="
git rev-list --all --objects \
  | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '/^blob/ {print $4}' \
  | grep -E "$SENSITIVE_REGEX" \
  | grep -v '^\.env\.example$' \
  | grep -v '^desktop-admin/\.env\.example$' \
  | grep -v '^dashboard/\.env\.production$' \
  | grep -v '^deployment/seller\.env\.example$' \
  | sort -u || true

echo
echo "Audit complete. If both sections are empty, history contains no committed .env/.pem/id.json blobs."
