@echo off
setlocal
python scripts\build_catalog.py || exit /b 1
python -m unittest discover -s tests -v || exit /b 1
python scripts\verify_repo.py || exit /b 1
echo CodeLayer Forge core is ready.
echo Browser shell: python -m http.server 4173 --directory apps/desktop/web
echo Native desktop: npm install ^&^& npm run desktop:dev
