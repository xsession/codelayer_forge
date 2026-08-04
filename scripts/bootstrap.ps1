$ErrorActionPreference = "Stop"
python scripts/build_catalog.py
python -m unittest discover -s tests -v
python scripts/verify_repo.py
Write-Host "CodeLayer Forge core is ready."
Write-Host "Browser shell: python -m http.server 4173 --directory apps/desktop/web"
Write-Host "Native desktop: npm install; npm run desktop:dev"
