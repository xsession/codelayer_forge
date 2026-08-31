#!/usr/bin/env python3
"""Generate a deterministic switching/ringing waveform for the RF perspective demo."""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", nargs="?", type=Path, default=Path("switching_waveform.csv"))
    parser.add_argument("--sample-rate", type=float, default=20e6)
    parser.add_argument("--duration", type=float, default=2e-3)
    parser.add_argument("--switching", type=float, default=250e3)
    args = parser.parse_args()
    count = int(args.sample_rate * args.duration)
    if count < 8 or count > 2_000_000:
        raise SystemExit("sample count must be between 8 and 2,000,000")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("time", "voltage"))
        for index in range(count):
            t = index / args.sample_rate
            square = 0.35 if math.sin(2 * math.pi * args.switching * t) >= 0 else -0.35
            ringing = 0.05 * math.sin(2 * math.pi * 3.2e6 * t)
            clock = 0.02 * math.sin(2 * math.pi * 8e6 * t)
            writer.writerow((f"{t:.12g}", f"{square + ringing + clock:.12g}"))


if __name__ == "__main__":
    main()
