# RF / EMC user workflow

Embeddyn's RF perspective is intended for two connected tasks:

1. **Antenna/network tuning** using Touchstone S-parameters and optional openEMS full-wave simulation.
2. **Generated-noise/pre-compliance inspection** using FFT analysis of simulated/session/measured waveforms.

The Studio UI makes these results easy to correlate visually with the system construction, while the CLI makes the workflow scriptable/reproducible.

## RF capability check

```bash
embeddyn rf status
```

The result distinguishes lightweight built-in analysis, optional scikit-rf capability, and external/native full-wave tooling.

## Antenna tuning loop

Recommended loop:

```text
actual PCB stack-up + target frequency
              |
              v
      analytical patch seed
              |
              v
     generated openEMS model
              |
              v
      full-wave S1P + pattern
              |
              v
     Embeddyn S11/Smith analysis
              |
              v
 resonance placement + impedance tuning
              |
              +---------- repeat ----------+
              |
              v
       prototype + VNA measurement
```

### Step 1 — use the actual stack-up

At RF frequencies, FR-4-like materials vary significantly. Use the laminate/vendor's RF-relevant dielectric constant and loss tangent if available. Enter copper/enclosure/feed/ground effects through the full-wave model rather than assuming the transmission-line seed is final.

### Step 2 — calculate a rectangular patch seed

```bash
embeddyn rf patch-seed \
  --target-hz 2.45e9 \
  --epsilon-r 4.4 \
  --substrate-mm 1.6
```

The seed returns patch width/length, effective dielectric constant, fringing extension, and wavelength-related values.

The analytical result is a **starting geometry**, not a fabrication guarantee.

### Step 3 — generate openEMS Python model

```bash
embeddyn rf patch-openems-script patch_2450.py \
  --target-hz 2.45e9 \
  --epsilon-r 4.4 \
  --substrate-mm 1.6 \
  --loss-tangent 0.02 \
  --z0 50
```

The generated model is standalone and writes results under `openems_patch_output/`, including `patch.s1p`, `summary.json`, and far-field CSV when NF2FF succeeds.

You can override patch width/length/feed offset for iterative tuning rather than regenerating only from the analytical seed.

### Step 4 — inspect S11

```bash
embeddyn rf touchstone openems_patch_output/patch.s1p \
  --target-hz 2.45e9 \
  --return-loss-db 10
```

Embeddyn reports:

- best resonance frequency,
- target-frequency S11,
- return loss,
- VSWR,
- complex input impedance,
- accepted-power fraction,
- threshold bandwidth,
- first-order tuning guidance.

### Step 5 — tune resonance before match

As a rule of thumb, place the resonance near the target before aggressively tuning the feed/matching network. If resonance is too low/high, the resonant electrical path is usually too long/short. Once placement is correct, tune feed position and any matching network for desired impedance/bandwidth.

### Step 6 — validate with measurement

Full-wave simulation is still a model. The enclosure, nearby conductors, battery/cables, plastic, solder mask, connector, user's hand, and manufacturing tolerance can all move the response. Measure the assembled prototype with a properly calibrated VNA and feed/de-embed appropriately.

## Studio RF/EMC cockpit

The cockpit is designed for visual analysis by eye.

### Construction panel

Shows a scale-proportional patch/substrate/ground/feed representation with stack-up labels. Project graph data is also scanned for likely high-edge-rate RF/noise sources such as clocks, switching power, PWM, digital buses, motors, and radios.

The source/coupling risk map is heuristic. It tells you where to inspect first; it does not calculate field coupling.

### Status cards

Separate status for:

- target match,
- resonance placement,
- EMI headroom,
- construction/full-wave readiness.

This prevents one strong metric from hiding a failure in another.

### S11 + Smith chart

Use the linked views to answer different questions:

- **S11 plot:** where is resonance and what bandwidth meets the return-loss threshold?
- **Smith chart:** how does impedance move, and is the mismatch mainly resistive/capacitive/inductive around target?

The cursor readout links frequency with S11/VSWR/impedance.

### Stale-result protection

If you change target frequency, Z0, stack-up, geometry, FFT assumptions, or limit masks, the previous result is marked stale. Re-run/re-import analysis before making a design decision.

## Generated RF-noise analysis

### Sources

Embeddyn can analyze:

- switching-node simulation CSV,
- supply/current proxy waveform,
- PWM/clock telemetry,
- an arbitrary numeric Studio session channel,
- measured waveform CSV.

### CLI

```bash
embeddyn rf noise switching.csv \
  --time-column time_s \
  --value-column switch_v \
  --value-unit V \
  --impedance-ohms 50 \
  --max-fft-points 16384 \
  --top-peaks 20
```

### Read the result correctly

The FFT reports spectrum/peaks and useful derived units. It also reports sampling-quality information such as Nyquist limit and frequency-bin resolution.

Before comparing to an emissions limit, ask:

1. Is the measured quantity voltage/current/field strength actually comparable to that limit?
2. Is the acquisition impedance correct?
3. Is the sample rate high enough?
4. Is timing uniform enough?
5. Is the simulated duration long enough for desired low-frequency resolution?
6. Does the applicable standard require detector behavior (quasi-peak/average), RBW/VBW, LISN, antenna factor, distance, cable arrangement, chamber/site, or other corrections not represented here?

### Engineering masks

Studio can overlay a user-supplied frequency/limit mask and show margin/exceedances. Treat this as a design target unless the mask and acquisition chain have been transformed into the exact units/method required by the applicable standard.

## What to inspect in a whole construction

When a harmonic or broadband problem appears, correlate the spectrum with:

- oscillator/PLL frequencies,
- MCU peripheral clocks,
- PWM/switching frequency and edges,
- DC/DC converter switch node and diode/rectifier recovery,
- SPI/QSPI/SDIO/USB/CAN edge rates,
- display/memory clocks,
- motor commutation,
- cable/common-mode paths,
- antenna/feed/ground proximity,
- enclosure seams and connector locations.

Look at harmonic spacing first. A repeated comb often points to a periodic source; broad shoulders can indicate very fast edges, ringing, modulation, spread spectrum, jitter, or multiple sources.

## Simulation-to-lab closure

A practical progression is:

1. schematic/SPICE edge/current analysis,
2. Embeddyn waveform FFT,
3. PCB/antenna full-wave model where relevant,
4. near-field probe scan and current probe/LISN pre-compliance,
5. VNA antenna/network measurement,
6. controlled pre-compliance chamber/site,
7. formal compliance test.

Use Embeddyn to keep the assumptions/results linked to the project, not to replace calibrated instruments.

For deeper implementation/limitations, see [RF / EMC perspective](../RF_EMC_PERSPECTIVE.md).
