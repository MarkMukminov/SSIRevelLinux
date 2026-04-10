#!/usr/bin/env python3
"""
tune_filters.py — auto-tune DEADBAND and RATE_ALPHA from a Revel baseline CSV.

Usage:
    python3 tune_filters.py <baseline_log.csv>

Record a short baseline (10-30 seconds, system at rest, no valve events).
Export it from Revel as CSV. Column headers must contain the PT channel names.

Outputs the two const lines to paste into both .rvl files.
"""

import sys
import csv
import math

# ── config ────────────────────────────────────────────────────────────────────
CYCLE = 0.1                 # seconds per Revel cycle
TARGET_DISPLAY_NOISE = 1.0  # PSI — max acceptable noise on smoothed pressure display
TARGET_RATE_NOISE   = 5.0   # PSI/min — max acceptable noise on rate traces
DEADBAND_SETTLE     = 10    # cycles to skip at start (filter settling)

CHANNELS = [
    'PT_n2_fill',
    'PT_ox_tank',
    'PT_ox_fill',
    'PT_fuel_tank',
    'PT_chamber',
    'LC_ox_tank',
    'LoadCell1',
    'LoadCell2',
    'LoadCell3',
    'TC0',
]
# ──────────────────────────────────────────────────────────────────────────────


def load_csv(path):
    """Load PT channel data from a Revel CSV export."""
    data = {ch: [] for ch in CHANNELS}
    found = set()
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: CSV has no header row.")
            sys.exit(1)
        for ch in CHANNELS:
            # fuzzy match — header might have spaces or mixed case
            for col in reader.fieldnames:
                if ch.lower() in col.lower():
                    found.add(ch)
                    break
        for row in reader:
            for ch in CHANNELS:
                for col in (reader.fieldnames or []):
                    if ch.lower() in col.lower():
                        try:
                            data[ch].append(float(row[col]))
                        except (ValueError, TypeError):
                            pass
                        break
    missing = [ch for ch in CHANNELS if ch not in found]
    if missing:
        print(f"WARNING: channels not found in CSV: {missing}")
        print(f"         Available columns: {reader.fieldnames}")
    return data


def std_dev(values):
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def simulate_pipeline(series, deadband, rate_alpha):
    """
    Simulate the full filter chain:
      1. Adaptive pressure smoother:  d³ / (d² + DEADBAND²)
      2. Rate computation from smoothed signal
      3. EMA on rates: RATE_ALPHA * raw_rate + (1-RATE_ALPHA) * prev_rate

    Returns (display_noise_std, rate_noise_std) in PSI and PSI/min.
    """
    if len(series) < DEADBAND_SETTLE + 2:
        return float('inf'), float('inf')

    db2 = deadband * deadband
    smoothed = series[0]
    prev_smooth = series[0]
    rate = 0.0

    smoothed_vals = []
    rate_vals = []

    for i, raw in enumerate(series[1:]):
        delta = raw - smoothed
        d2 = delta * delta
        smoothed = smoothed + d2 * delta / (d2 + db2)

        raw_rate = (smoothed - prev_smooth) / CYCLE * 60.0
        rate = rate_alpha * raw_rate + (1.0 - rate_alpha) * rate

        prev_smooth = smoothed
        if i >= DEADBAND_SETTLE:
            smoothed_vals.append(smoothed)
            rate_vals.append(rate)

    return std_dev(smoothed_vals), std_dev(rate_vals)


def sweep(series, label, deadband_candidates, alpha_candidates):
    """
    Two-phase sweep:
      Phase 1 — find smallest DEADBAND where display noise < TARGET_DISPLAY_NOISE
      Phase 2 — fix that DEADBAND, find smallest RATE_ALPHA where rate noise < TARGET_RATE_NOISE
    """
    print(f"\n── {label} ({'%d samples' % len(series)}) ──")

    # Phase 1: DEADBAND sweep (fix alpha=1.0 to see raw rate noise baseline)
    print(f"  Phase 1 — DEADBAND sweep (target display noise < {TARGET_DISPLAY_NOISE} PSI)")
    chosen_deadband = deadband_candidates[-1]
    for db in deadband_candidates:
        disp_noise, _ = simulate_pipeline(series, db, 1.0)
        flag = '✓' if disp_noise <= TARGET_DISPLAY_NOISE else ''
        print(f"    DEADBAND={db:.1f}  display noise={disp_noise:.3f} PSI  {flag}")
        if disp_noise <= TARGET_DISPLAY_NOISE:
            chosen_deadband = db
            break

    # Phase 2: RATE_ALPHA sweep
    print(f"  Phase 2 — RATE_ALPHA sweep (target rate noise < {TARGET_RATE_NOISE} PSI/min, DEADBAND={chosen_deadband:.1f})")
    chosen_alpha = alpha_candidates[-1]
    for alpha in alpha_candidates:
        _, rate_noise = simulate_pipeline(series, chosen_deadband, alpha)
        flag = '✓' if rate_noise <= TARGET_RATE_NOISE else ''
        print(f"    RATE_ALPHA={alpha:.2f}  rate noise={rate_noise:.2f} PSI/min  {flag}")
        if rate_noise <= TARGET_RATE_NOISE:
            chosen_alpha = alpha
            break

    return chosen_deadband, chosen_alpha


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    path = sys.argv[1]
    print(f"Loading: {path}")
    data = load_csv(path)

    usable = {ch: s for ch, s in data.items() if len(s) >= DEADBAND_SETTLE + 10}
    if not usable:
        print("ERROR: no usable channel data found (need at least 20 samples per channel).")
        sys.exit(1)

    # Candidate sweep ranges
    deadband_candidates = [round(v * 0.1, 1) for v in range(1, 51)]   # 0.1 → 5.0 PSI
    alpha_candidates    = [round(v * 0.01, 2) for v in range(1, 101)]  # 0.01 → 1.00

    results = {}
    for ch, series in usable.items():
        db, alpha = sweep(series, ch, deadband_candidates, alpha_candidates)
        results[ch] = (db, alpha)

    # Worst-case across all channels (most conservative)
    worst_db    = max(db    for db, _     in results.values())
    worst_alpha = max(alpha for _,  alpha in results.values())

    print("\n" + "=" * 60)
    print("RESULTS PER CHANNEL")
    print("=" * 60)
    for ch, (db, alpha) in results.items():
        print(f"  {ch:<20}  DEADBAND={db:.1f}  RATE_ALPHA={alpha:.2f}")

    print("\n" + "=" * 60)
    print("PASTE INTO BOTH .rvl FILES  (worst-case across all channels)")
    print("=" * 60)
    print(f"const DEADBAND:float = {worst_db:.1f}      #PSI — auto-tuned {path}")
    print(f"const RATE_ALPHA:float = {worst_alpha:.2f}     #EMA — auto-tuned for <{TARGET_RATE_NOISE} PSI/min rate noise")
    print("=" * 60)


if __name__ == '__main__':
    main()
