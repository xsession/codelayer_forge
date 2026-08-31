# First project quick start

This guide gives three independent quick starts. You do not need the full external simulator stack to learn Embeddyn.

## 1. Start Local Studio

Bootstrap:

```bash
python3 bootstrap.py bootstrap --profile studio
. ./.embeddyn/env.sh
```

Check the local environment:

```bash
embeddyn studio doctor
```

Start Studio:

```bash
embeddyn studio run
```

By default Studio listens on `127.0.0.1:9010` and opens a browser. The UI gives access to projects, component search, firmware/assets, sessions/telemetry, and RF/EMC analysis when RF dependencies are installed.

A useful first exercise is:

1. Search the bundled component catalog by MCU/bus/vendor.
2. Create or load a project graph.
3. Upload a small ELF/HEX/UF2 firmware image and run local firmware analysis.
4. Inspect format, architecture inference, strings, vector-table/disassembly information, and security-oriented findings.
5. Start a supported emulation session or ingest telemetry and explore plots/filters.

## 2. Run deterministic co-simulation with mock adapters

The supplied DC motor project demonstrates signal coupling without requiring Renode, ngspice, or Webots:

```bash
embeddyn mechatronics validate examples/mechatronics/dc-motor.yaml
embeddyn mechatronics run examples/mechatronics/dc-motor.yaml --mock
```

The project models:

```text
firmware PWM duty
       |
       v
electrical motor current -----> mechanical torque/velocity
       ^                                |
       |                                |
       +----------- back EMF <----------+
                                        |
                                        +--> firmware measured velocity
```

Inspect stored runs:

```bash
embeddyn mechatronics runs-list
```

Then inspect a chosen run ID:

```bash
embeddyn mechatronics runs-inspect RUN_ID
```

The mock run is valuable because it validates project structure, scheduler/coupling behavior, storage, and telemetry before external processes are introduced.

## 3. Run the RF/EMC example

Bootstrap the RF profile if needed:

```bash
python3 bootstrap.py bootstrap --profile rf
. ./.embeddyn/env.sh
```

Check solver/backend availability:

```bash
embeddyn rf status
```

Analyze the provided antenna fixture:

```bash
embeddyn rf touchstone examples/rf/antenna_fixture.s1p --target-hz 2.4e9
```

Create a 2.45 GHz FR-4-like patch starting point:

```bash
embeddyn rf patch-seed \
  --target-hz 2.45e9 \
  --epsilon-r 4.4 \
  --substrate-mm 1.6
```

Generate the standalone openEMS model:

```bash
embeddyn rf patch-openems-script patch_2450.py \
  --target-hz 2.45e9 \
  --epsilon-r 4.4 \
  --substrate-mm 1.6 \
  --loss-tangent 0.02
```

For generated-noise analysis, create a fixture waveform and analyze it:

```bash
python examples/rf/generate_switching_waveform.py
embeddyn rf noise examples/rf/switching_waveform.csv
```

If the generator writes to another path, use that generated CSV path. The Studio RF/EMC cockpit gives the most visual workflow: construction view, S11, Smith chart, resonance/tuning guidance, EMI spectrum, harmonic markers, masks, and stale-analysis warnings.

## Where to go next

- Studio users: [Local Studio](STUDIO.md)
- Build/CLI users: [CLI reference](CLI_REFERENCE.md)
- Simulation users: [Mechatronics](MECHATRONICS.md)
- RF users: [RF / EMC](RF_EMC.md)
- File/data questions: [Projects and data](PROJECTS_AND_DATA.md)
