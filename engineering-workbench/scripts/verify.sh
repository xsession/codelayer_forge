#!/usr/bin/env sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"
node --check standalone/app.js
node --check standalone/router.js
node tests/standalone-router.mjs
if command -v tsc >/dev/null 2>&1; then
  tsc -p tsconfig.corecheck.json
elif [ -x /opt/nvm/versions/node/v22.16.0/bin/tsc ]; then
  /opt/nvm/versions/node/v22.16.0/bin/tsc -p tsconfig.corecheck.json
else
  echo "TypeScript compiler not found; skipped core type-check."
fi
echo "Verification complete."
