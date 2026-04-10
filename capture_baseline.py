#!/usr/bin/env python3
"""
capture_baseline.py — record live Revel channel data during calibration.

Usage:
    python3 capture_baseline.py [revel_host]

Revel host defaults to 172.16.23.1

Workflow:
  1. Run this script
  2. It waits for you to click "Cal_Cmd" button in the Revel dashboard
  3. Captures 10 seconds of live raw channel data
  4. Saves as baseline_calibration.csv
  5. Then run: python3 tune_filters.py baseline_calibration.csv
"""

import sys
import time
import csv
import requests
from datetime import datetime

REVEL_HOST = "172.16.23.1"
POLL_INTERVAL = 0.05  # 50ms polls (faster than 0.1s cycle for good coverage)
TIMEOUT = 120  # max wait for calibration to complete

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

CONTROL_CHANNELS = ['Cal_Cmd', 'Cal_Active', 'Cal_Done']


def get_channel(host, channel_name):
    """Query Revel REST API for a single channel value."""
    try:
        # Try the standard Revel API endpoint
        response = requests.get(
            f"http://{host}/api/channels/{channel_name}",
            timeout=2,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('value')
    except Exception:
        pass

    # Fallback: try alternate endpoint
    try:
        response = requests.get(
            f"http://{host}:8080/api/channels/{channel_name}",
            timeout=2,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get('value')
    except Exception:
        pass

    return None


def get_channels(host, channel_list):
    """Get values for multiple channels."""
    values = {}
    for ch in channel_list:
        values[ch] = get_channel(host, ch)
    return values


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else REVEL_HOST

    print(f"Connecting to Revel at {host}...")
    print()

    # Test connection
    try:
        test = get_channel(host, 'PT_n2_fill')
        if test is None:
            print(f"WARNING: Could not query channels from {host}")
            print("Make sure Revel is running and accessible.")
            print()
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    print("=" * 60)
    print("READY — Waiting for calibration start...")
    print("  Click 'Cal_Cmd' button in Revel dashboard")
    print("  (keep system at idle/steady state)")
    print("=" * 60)
    print()

    # Poll for Cal_Cmd becoming True
    start_wait = time.time()
    while time.time() - start_wait < TIMEOUT:
        status = get_channels(host, CONTROL_CHANNELS)
        if status.get('Cal_Active'):
            print("✓ Calibration started, recording...")
            break
        time.sleep(0.5)
    else:
        print("TIMEOUT: No calibration started within 2 minutes.")
        sys.exit(1)

    # Record data while Cal_Active is True
    recorded = []
    cal_done = False
    record_start = time.time()

    while not cal_done and (time.time() - record_start) < 15:  # 15s safety timeout
        values = get_channels(host, CHANNELS + CONTROL_CHANNELS)
        recorded.append({ch: values.get(ch) for ch in CHANNELS})

        cal_done = values.get('Cal_Done', False)
        time.sleep(POLL_INTERVAL)

    elapsed = time.time() - record_start
    print(f"✓ Calibration done. Recorded {len(recorded)} samples in {elapsed:.1f}s")
    print()

    # Write CSV
    output_file = 'baseline_calibration.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CHANNELS)
        writer.writeheader()
        for row in recorded:
            writer.writerow(row)

    print("=" * 60)
    print(f"Saved: {output_file}")
    print(f"  {len(recorded)} samples × {len(CHANNELS)} channels")
    print()
    print("Next step:")
    print(f"  python3 tune_filters.py {output_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
