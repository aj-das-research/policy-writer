#!/bin/bash
# Build the LMS submission ZIP: report PDF + executed notebook + all code and result files. Refuses to package secrets.
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${1:-submission/policy-writer-submission.zip}
mkdir -p "$(dirname "$OUT")"
rm -f "$OUT"
git ls-files -z | xargs -0 zip -q "$OUT"   # tracked files only: never .env, venv, caches
zip -q "$OUT" report/report.pdf notebooks/reproduce_numbers.ipynb
if unzip -p "$OUT" | grep -aqE 'sk-[A-Za-z0-9_-]{20,}'; then
  echo "[submission] API-key-like string found in $OUT; refusing" >&2; rm -f "$OUT"; exit 1
fi
if unzip -l "$OUT" | grep -qE '(^|/)\.env'; then
  echo "[submission] .env found in $OUT; refusing" >&2; rm -f "$OUT"; exit 1
fi
echo "[submission] $OUT ($(du -h "$OUT" | cut -f1)), $(unzip -l "$OUT" | tail -1 | awk '{print $2}') files; no secrets found"
