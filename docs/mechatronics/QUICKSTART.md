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

Export a KiCad schematic for SPICE simulation:

```bash
embeddyn mechatronics kicad-export electronics/controller.kicad_sch \
  --output artifacts/kicad/controller.cir
embeddyn mechatronics kicad-plugin plugins/kicad-embeddyn-bridge
```

For Webots, copy `examples/mechatronics/controllers/embeddyn_bridge` into the world's controller search path. Replace the reference plant equations with field and device access for the actual PROTO model.
