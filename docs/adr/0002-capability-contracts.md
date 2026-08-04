# ADR 0002: Capability contracts

- Status: Accepted
- Date: 2026-08-03

Plugins depend on named, semantic-versioned capabilities instead of importing another plugin's implementation. This keeps Route Core reusable and lets OpenHDL Designer evolve independently from pin planning and future graphical editors.
