# Contributing

1. Create an issue or architecture decision record for changes to public contracts.
2. Keep plugin APIs backward compatible within a major API line.
3. Add tests for all behavior changes.
4. Run `python3 scripts/verify_repo.py` and the relevant language test suites.
5. Use conventional commits: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `build:`, `ci:`.

Generated files must be reproducible. Do not commit secrets, private device data or vendor files whose redistribution terms are unclear.
