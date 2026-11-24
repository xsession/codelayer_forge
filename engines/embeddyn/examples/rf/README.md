# RF perspective examples

Analyze the synthetic antenna fixture:

```bash
embeddyn rf touchstone examples/rf/antenna_fixture.s1p --target-hz 2.45e9
```

Generate and analyze a switching waveform:

```bash
python examples/rf/generate_switching_waveform.py /tmp/switching.csv
embeddyn rf noise /tmp/switching.csv --impedance-ohms 50
```

These files are functional test/demo inputs, not calibrated RF measurements.
