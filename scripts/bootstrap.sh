#!/usr/bin/env sh
set -eu

python3 scripts/build_catalog.py
python3 -m unittest discover -s tests -v
python3 scripts/verify_repo.py

cat <<'EOF'
CodeLayer Forge core is ready.
Run the browser shell with:
  python3 -m http.server 4173 --directory apps/desktop/web
Build the native desktop after installing Rust and Tauri prerequisites:
  npm install
  npm run desktop:dev
EOF
