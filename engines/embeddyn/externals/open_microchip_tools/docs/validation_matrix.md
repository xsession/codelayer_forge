# Validation Matrix

This matrix maps common change types to the minimum expected validation scope.

| Change Type | Minimum Validation | Typical Supporting Checks |
| --- | --- | --- |
| Python protocol logic | focused `unittest` module | editor diagnostics, related demo command |
| Zephyr C logic | local diagnostics and nearest behavior check | focused host mirror tests, docs update |
| Machine-readable artifact | parse/read artifact directly | traceability and docs alignment |
| Documentation-only | editor diagnostics on touched docs | validate referenced commands where practical |
| PK4 recovery model | focused recovery/session/profile tests | manifest parse, docs and traceability review |

## Current High-value Validation Paths

- `tests.test_pk4_observed_profile`
- `tests.test_zephyr_pk4_observed_session`
- `tests.test_zephyr_demo`
- `tests.test_pk4_recovery_project`

## Operational Checks

When a docs change introduces or updates a command example, prefer running at least one representative command from the edited set.