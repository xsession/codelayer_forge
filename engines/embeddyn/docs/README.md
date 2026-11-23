# Embeddyn documentation

This directory is the documentation portal for Embeddyn. Start with the track that matches what you are trying to do.

## User documentation

| Document | Use it when |
|---|---|
| [User guide](user/README.md) | You want a map of the product and the recommended learning path. |
| [Installation and bootstrap](user/INSTALLATION.md) | You need a reproducible workstation, Studio, RF, or full simulation environment. |
| [First project quick start](user/QUICKSTART.md) | You want to get from a clean checkout to a useful run quickly. |
| [Local Studio](user/STUDIO.md) | You use the browser UI for projects, assets, firmware, telemetry, RF/EMC, and observability. |
| [CLI reference](user/CLI_REFERENCE.md) | You need the command groups, common options, and examples. |
| [Projects, data, and file formats](user/PROJECTS_AND_DATA.md) | You need to understand workspaces, project graphs, assets, telemetry, specifications, and persisted data. |
| [Mechatronics and digital-twin workflows](user/MECHATRONICS.md) | You couple firmware, SPICE, mechanics, HIL, distributed workers, experiments, or digital-twin evidence. |
| [RF / EMC workflows](user/RF_EMC.md) | You tune antennas or inspect generated RF noise/pre-compliance spectra. |
| [Troubleshooting](user/TROUBLESHOOTING.md) | A bootstrap, build, simulator, Studio, worker, or RF workflow is not behaving as expected. |

## Contributor documentation

| Document | Use it when |
|---|---|
| [Contributor guide](contributing/README.md) | You are preparing a change or want the development workflow. |
| [Development setup](contributing/DEVELOPMENT_SETUP.md) | You need a development environment and repository checks. |
| [Architecture](contributing/ARCHITECTURE.md) | You need the code-level architecture and subsystem responsibilities. |
| [Code organization](contributing/CODE_ORGANIZATION.md) | You need to find the correct module, tests, examples, or documentation. |
| [Testing and validation](contributing/TESTING.md) | You are adding or changing behavior and need the correct verification layer. |
| [Extension recipes](contributing/EXTENDING.md) | You are adding an API, UI capability, simulator adapter, importer, RF feature, or CLI command. |
| [Data model and migrations](contributing/DATA_AND_MIGRATIONS.md) | You are changing SQLite schemas, artifact layouts, manifests, telemetry, or compatibility. |
| [Security model](contributing/SECURITY.md) | You are changing process execution, uploads, remote access, external tools, or persisted user data. |
| [Release and dependency policy](contributing/RELEASE.md) | You are changing versions, locked source dependencies, packaging, or release artifacts. |

A short root-level [CONTRIBUTING.md](../CONTRIBUTING.md) points contributors here so Git hosting UIs discover the guide automatically.

## C4 architecture documentation

The C4 documentation describes the system at multiple zoom levels. The diagrams use Mermaid so they remain readable in plain Markdown and render on common Git hosting platforms.

1. [C4 overview and notation](c4/README.md)
2. [C1 — System context](c4/C1_CONTEXT.md)
3. [C2 — Containers](c4/C2_CONTAINERS.md)
4. [C3 — Components](c4/C3_COMPONENTS.md)
5. [Dynamic views](c4/DYNAMIC_VIEWS.md)
6. [Deployment view](c4/DEPLOYMENT.md)
7. [Architectural boundaries and decisions](c4/DECISIONS_AND_BOUNDARIES.md)

## Existing specialist documentation

These documents remain authoritative for the deeper topic they cover and are linked from the user/contributor guides where relevant:

- [Bootstrap and dependency versioning](BOOTSTRAP_AND_DEPENDENCY_VERSIONING.md)
- [RF / EMC perspective](RF_EMC_PERSPECTIVE.md)
- [Local Studio architecture](LOCAL_STUDIO_ARCHITECTURE.md)
- [Observability](OBSERVABILITY.md)
- [Reverse engineering](REVERSE_ENGINEERING.md)
- [Local security](SECURITY_LOCAL.md)
- [Local deployment](DEPLOYMENT_LOCAL.md)
- [Mechatronics architecture](mechatronics/ARCHITECTURE.md)
- [Mechatronics quick start](mechatronics/QUICKSTART.md)
- [Implementation status](mechatronics/IMPLEMENTATION_STATUS.md)

## Documentation principles

- **Task first:** user docs describe outcomes before internals.
- **Source grounded:** commands, paths, API routes, and ownership boundaries are derived from the current repository.
- **Local-first:** offline and deterministic behavior is described as the default where the implementation supports it.
- **No false validation claims:** full-wave, HIL, physical RF, or external simulator results are distinguished from mocks and pre-compliance estimates.
- **One source of truth:** specialist documents are linked rather than copied wholesale.
