#!/usr/bin/env python3
"""
capture_baseline.py — record live Revel channel data during calibration.

Usage:
    python3 capture_baseline.py [revel_host]

Revel host defaults to 172.16.1.10 (change if your dashboard is on a different IP)

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

REVEL_HOST = "172.16.1.10"  # Revel dashboard IP
POLL_INTERVAL = 0.05  # 50ms polls (faster than 0.1s cycle for good coverage)
TIMEOUT = 120  # max wait for calibration to complete
API_ENDPOINTS = [
    "http://{host}:5000/api/channels/{channel}",      # common Revel port
    "http://{host}/api/channels/{channel}",
    "http://{host}:8080/api/channels/{channel}",
]

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


_api_endpoint = None  # cache working endpoint

def get_channel(host, channel_name):
    """Query Revel REST API for a single channel value."""
    global _api_endpoint

    # Try cached endpoint first
    if _api_endpoint:
        try:
            url = _api_endpoint.format(host=host, channel=channel_name)
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                data = response.json()
                return data.get('value')
        except Exception:
            _api_endpoint = None  # endpoint failed, try again

    # Try each API endpoint until one works
    for endpoint_template in API_ENDPOINTS:
        try:
            url = endpoint_template.format(host=host, channel=channel_name)
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                data = response.json()
                _api_endpoint = endpoint_template  # found working endpoint
                return data.get('value')
        except Exception:
            continue

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
    test = get_channel(host, 'PT_n2_fill')
    if test is None:
        print(f"WARNING: Could not reach API on {host}")
        print("Trying alternate hosts...")
        for alt_host in ['172.16.23.1', '172.16.1.10', 'localhost']:
            test = get_channel(alt_host, 'PT_n2_fill')
            if test is not None:
                host = alt_host
                print(f"✓ Found Revel at {host}")
                break
        if test is None:
            print(f"ERROR: Could not connect to Revel on any host")
            print(f"  Tried: {host}, 172.16.23.1, 172.16.1.10, localhost")
            print()
            print("Debug: check if Revel is running and what IP/port the dashboard uses")
            sys.exit(1)

    print("=" * 60)
    print("READY — Waiting for calibration start...")
    print("  Click 'Cal_Cmd' button in Revel dashboard")
    print("  (keep system at idle/steady state)")
    print("=" * 60)
    print()

    # Poll for Cal_Active becoming True
    start_wait = time.time()
    print("Polling for Cal_Active... (waiting for you to click Cal_Cmd in dashboard)")
    while time.time() - start_wait < TIMEOUT:
        status = get_channels(host, CONTROL_CHANNELS)
        cal_active = status.get('Cal_Active')
        if cal_active:
            print(f"  ✓ Cal_Active detected (True)!")
            break
        # Show dots while waiting
        if int((time.time() - start_wait) * 2) % 2 == 0:
            print(".", end="", flush=True)
        time.sleep(0.5)
    else:
        print("\nTIMEOUT: Cal_Active never went True within 2 minutes.")
        print("  Debug: Check that the button click actually sets Cal_Active in Revel UI")
        sys.exit(1)
    print()

    # Record data while Cal_Active is True
    recorded = []
    cal_done = False
    record_start = time.time()
    last_status_time = record_start

    while not cal_done and (time.time() - record_start) < 15:  # 15s safety timeout
        values = get_channels(host, CHANNELS + CONTROL_CHANNELS)

        cal_active = values.get('Cal_Active', False)
        cal_done = values.get('Cal_Done', False)

        if cal_active:
            recorded.append({ch: values.get(ch) for ch in CHANNELS})

        # Status update every 2 seconds
        if time.time() - last_status_time > 2:
            elapsed = time.time() - record_start
            print(f"  Recording... {len(recorded)} samples in {elapsed:.1f}s (Cal_Active={cal_active}, Cal_Done={cal_done})")
            last_status_time = time.time()

        if not cal_active and len(recorded) > 0:
            # Cal_Active went False and we have data
            break

        time.sleep(POLL_INTERVAL)

    elapsed = time.time() - record_start
    print()
    print(f"✓ Recording stopped. Captured {len(recorded)} samples in {elapsed:.1f}s")
    print()

    if len(recorded) < 10:
        print("WARNING: Very few samples captured.")
        print("  Make sure Cal_Active stays True during recording.")
        print("  Check Revel dashboard to confirm Cal_Active is displayed as True.")
        if len(recorded) == 0:
            print("\nERROR: No data recorded! Check API connectivity.")
            sys.exit(1)

    # Write CSV
    output_file = 'baseline_calibration.csv'
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=CHANNELS)
        writer.writeheader()
        for row in recorded:
            writer.writerow(row)

    print("=" * 60)
    print(f"✓ Saved: {output_file}")
    print(f"  {len(recorded)} samples × {len(CHANNELS)} channels")
    print()
    print("Next step:")
    print(f"  python3 tune_filters.py {output_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
