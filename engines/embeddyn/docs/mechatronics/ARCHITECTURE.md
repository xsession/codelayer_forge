# Mechatronic co-simulation architecture

Embeddyn now has a fourth, system-level layer above the existing graph editor, firmware build and Renode emulation:

```text
Embeddyn graph / project YAML
        |
        v
Co-simulation master (fixed macro step, deterministic ordering)
  | firmware         | electrical             | mechanical
  | Renode/socket    | ngspice or LTspice     | Webots Supervisor bridge
  +------------------+-------------------------+
        |
        v
Unified signal bus -> CSV/telemetry -> Studio plots, scope, spectrum, logic analyzer
```

The integration is signal-oriented rather than simulator-specific. A project declares typed signals and explicit couplings. Adapters translate those signals into each simulator's native transport. This means Webots PROTO models, SPICE netlists and Renode peripherals can evolve independently.

## Master algorithm

The current master uses a deterministic fixed macro step and executes firmware, electrical and mechanical domains in that order. Feedback paths should use `delay_steps: 1`; this breaks algebraic loops and makes replay deterministic. This is suitable for controller development, fault injection, regression tests and many electromechanical plants.

High-stiffness power-electronics or contact systems may need smaller macro steps, sub-stepping, waveform relaxation or an FMI-based iterative master. The adapter interfaces are intentionally small so those algorithms can be added without changing project files.

## Mechanical domain: Webots

`WebotsAdapter` starts Webots in fast batch mode and connects to a Supervisor controller over a local line-delimited JSON socket. The supplied reference controller demonstrates the protocol. Real projects should map Embeddyn signals to Webots motors, joints, contact sensors, force sensors, GPS/IMU, cameras and environmental fields.

## Electrical domain

`NgspiceAdapter` is the portable default. `LTspiceAdapter` supports detailed vendor-model validation in batch mode. Both use netlist templates with `{{signal.name}}` substitutions. LTspice process-per-step execution is intentionally treated as a validation backend; for high-frequency co-simulation use ngspice shared-library integration or a persistent bridge.

## KiCad integration

`embeddyn mechatronics kicad-export` calls `kicad-cli` to export a SPICE netlist from a schematic. `kicad-plugin` creates a KiCad IPC plugin skeleton that can send selected schematic context to the local Studio API. The plugin avoids editing or parsing KiCad's internal files and can be completed against the exact KiCad release's `kicad-python` API.

## Safety and limitations

This software is an engineering simulator, not a safety-certified digital twin. Validate models against measurements before using results for thermal, current, force, clearance, lifetime or human-safety decisions. Real-time hardware-in-the-loop requires deadline monitoring and a fail-safe I/O layer not supplied by the offline scheduler.
