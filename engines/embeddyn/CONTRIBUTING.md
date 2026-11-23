# Contributing to Embeddyn

Thank you for contributing. Embeddyn spans embedded build generation, browser tooling, firmware analysis, multi-domain co-simulation, distributed experiments, HIL safety, digital-twin workflows, and RF/EMC analysis, so changes should be made in the subsystem that owns the behavior rather than in a cross-cutting shortcut.

The complete contributor documentation is in [`docs/contributing/README.md`](docs/contributing/README.md).

Before submitting a change:

1. Bootstrap the `dev` profile: `python3 bootstrap.py bootstrap --profile dev`.
2. Activate the generated environment.
3. Run the targeted tests for the subsystem you changed.
4. Run the first-party suite: `pytest`.
5. Run `python -m compileall -q embeddyn vsd`.
6. For Studio changes, also validate `embeddyn/local/static/app.js` syntax and visually exercise the affected workflow.
7. Update user, contributor, and/or C4 documentation when behavior, interfaces, dependencies, deployment, or ownership boundaries change.

See the detailed guides for architecture, extension recipes, security, data migrations, tests, and release/dependency policy.
