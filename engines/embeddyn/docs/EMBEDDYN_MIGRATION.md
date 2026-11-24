# Migrating from VSD to Embeddyn

## CLI

Use `embeddyn` instead of `vsd`:

```bash
embeddyn init workspace
embeddyn run
embeddyn mechatronics run examples/mechatronics/dc-motor.yaml --mock
```

The old `vsd` executable is retained as a compatibility alias.

## Python imports

New code should use:

```python
from embeddyn.mechatronics import ...
```

instead of `vsd.*`.

## Environment variables

Preferred variables now use `EMBEDDYN_`:

- `EMBEDDYN_WORKSPACE`
- `EMBEDDYN_LOCAL_DATA_DIR`
- `EMBEDDYN_STUDIO_HOST`
- `EMBEDDYN_STUDIO_PORT`
- `EMBEDDYN_STUDIO_TOKEN`
- `EMBEDDYN_LIBRARY_DIR`
- `EMBEDDYN_COSIM_HOST`
- `EMBEDDYN_COSIM_PORT`

Core local runtime paths accept matching legacy `VSD_*` variables during migration.
