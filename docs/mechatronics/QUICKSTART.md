# Quick start

Run the deterministic built-in three-domain example:

```bash
pip install -e .
embeddyn mechatronics validate examples/mechatronics/dc-motor.yaml
embeddyn mechatronics run examples/mechatronics/dc-motor.yaml --mock \
  --output artifacts/mechatronics/dc-motor.csv
```

Inspect installed external tools:

```bash
embeddyn mechatronics doctor
```

Switch the YAML backends from `mock` to `webots`, `ngspice`, `ltspice` or `renode` as the corresponding models and executables become available.

For firmware-in-the-loop with Renode, start from `examples/mechatronics/dc-motor-renode.yaml` and read [RENODE.md](RENODE.md).
For a switching circuit in ngspice, start from `examples/mechatronics/dc-motor-ngspice.yaml` (or `dc-motor-full.yaml` with Renode firmware too) and read [NGSPICE.md](NGSPICE.md).
For a geared servo with backlash, friction and thermal feedback, and for automatic gain tuning (`embeddyn mechatronics tune examples/mechatronics/tuning/servo-pi.yaml`), read [TUNING.md](TUNING.md).
For systems with several controllers, motors or FMUs (named simulator instances), start from `examples/mechatronics/two-wheel-drive.yaml` and read [INSTANCES_AND_FMI.md](INSTANCES_AND_FMI.md).
To check a model (energy balance, step-size convergence, golden waveforms, scenarios), run `embeddyn mechatronics verify examples/mechatronics/dc-motor.yaml` and read [VERIFICATION.md](VERIFICATION.md).
To fit physical parameters to bench measurements, run `embeddyn mechatronics estimate examples/mechatronics/estimation/dc-motor.yaml` and read [ESTIMATION.md](ESTIMATION.md).

Export a KiCad schematic for SPICE simulation:

```bash
embeddyn mechatronics kicad-export electronics/controller.kicad_sch \
  --output artifacts/kicad/controller.cir
embeddyn mechatronics kicad-plugin plugins/kicad-embeddyn-bridge
```

For Webots, copy `examples/mechatronics/controllers/embeddyn_bridge` into the world's controller search path. Replace the reference plant equations with field and device access for the actual PROTO model.
