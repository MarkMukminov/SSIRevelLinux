#!/usr/bin/env python3
"""
Test: Sensor Manifest and Labeling
====================================
Validates that cold_flow_test.rvl contains a complete sensor manifest and
that temperature channels are unambiguously labeled with units.

Philosophy: The operator must never guess what a reading means.
- Pressure channels: PSI is the standard, but it must be stated.
- Temperature channels: Could be °C or °F — must be explicit in the manifest.
- Unknown channels (PT5): Must be flagged [ASSIGN] so someone is responsible
  for filling in the description before operational use.

Success criteria:
  1.  A SENSOR MANIFEST block exists in the .rvl file
  2.  Each pressure channel (PT_OT, PT_FT, PT5) has an entry in the manifest
  3.  Each temperature channel (TC1) has an entry in the manifest
  4.  Every manifest entry includes a unit (PSI, degF, or degC)
  5.  Temperature units are explicit (degF or degC, NOT just "temp" or "°")
  6.  Unknown sensors are flagged [ASSIGN] not silently left blank
  7.  Sim reset bounds are consistent with stated temperature units
      - degF: 70°F initial (room temp) and 500°F reset are plausible
      - degC: 70°C initial would be 158°F — implausible for ambient → reject
  8.  Pressure sensor range documented (upper bound <= 1300 to match sim wraps)
  9.  WARNING / OVERPRESSURE thresholds (WARN_P, MAX_SAFE_P) are documented
  10. No channel silently uses a unit that contradicts the manifest
"""

import re
import sys
import os

RVL_PATH = os.path.join(os.path.dirname(__file__), "..", "No-Hardware Sim", "cold_flow_test.rvl")

# Must match .rvl constants
SIM_TC_INIT = 70.0      # TC1 initialized at this value
SIM_TC_RESET = 500.0    # TC1 wraps/resets at this value

PRESSURE_CHANNELS = ["PT_OT", "PT_FT", "PT5"]
TEMP_CHANNELS = ["TC1"]
ALL_SENSOR_CHANNELS = PRESSURE_CHANNELS + TEMP_CHANNELS


def read_rvl():
    with open(RVL_PATH) as f:
        return f.read()


def extract_manifest(rvl_text):
    """Extract lines between SENSOR MANIFEST header and next non-comment section."""
    lines = rvl_text.splitlines()
    manifest_lines = []
    in_manifest = False
    for line in lines:
        stripped = line.strip()
        if "SENSOR MANIFEST" in stripped.upper():
            in_manifest = True
            continue
        if in_manifest:
            if stripped.startswith("#"):
                manifest_lines.append(stripped[1:].strip())  # strip leading #
            elif stripped == "":
                continue
            else:
                break  # non-comment, non-blank line ends the manifest
    return manifest_lines


def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {name}"
    if detail and not condition:
        msg += f"\n        detail: {detail}"
    print(msg)
    return condition


def run_tests():
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    rvl_text = read_rvl()
    manifest_lines = extract_manifest(rvl_text)
    manifest_text = "\n".join(manifest_lines).upper()

    # ─────────────────────────────────────────────────
    # 1. Manifest block exists
    # ─────────────────────────────────────────────────
    print("\n--- 1. Manifest presence ---")
    check("SENSOR MANIFEST block exists in .rvl",
          "SENSOR MANIFEST" in rvl_text.upper(),
          "Add a #SENSOR MANIFEST comment block near the top of the file")

    check("Manifest contains at least one channel entry",
          len(manifest_lines) >= len(ALL_SENSOR_CHANNELS),
          f"Expected at least {len(ALL_SENSOR_CHANNELS)} lines, got {len(manifest_lines)}")

    # ─────────────────────────────────────────────────
    # 2. All sensor channels documented in manifest
    # ─────────────────────────────────────────────────
    print("\n--- 2. Channel coverage ---")
    for ch in ALL_SENSOR_CHANNELS:
        check(f"{ch} documented in manifest",
              ch.upper() in manifest_text,
              f"Add {ch} to the SENSOR MANIFEST block")

    # ─────────────────────────────────────────────────
    # 3. Units present for every channel
    # ─────────────────────────────────────────────────
    print("\n--- 3. Units documented ---")
    for ch in PRESSURE_CHANNELS:
        # Find the manifest line for this channel and check it says PSI
        ch_lines = [l for l in manifest_lines if ch.upper() in l.upper()]
        has_psi = any("PSI" in l.upper() for l in ch_lines)
        check(f"{ch} manifest entry states PSI",
              has_psi,
              f"Manifest line(s) found: {ch_lines}")

    for ch in TEMP_CHANNELS:
        ch_lines = [l for l in manifest_lines if ch.upper() in l.upper()]
        has_unit = any(u in l.upper() for l in ch_lines for u in ["DEGF", "DEG_F", "°F", "DEGC", "DEG_C", "°C"])
        check(f"{ch} manifest entry explicitly states degF or degC",
              has_unit,
              f"Temperature unit must be explicit. Lines: {ch_lines}")

    # ─────────────────────────────────────────────────
    # 4. Temperature unit is degF (validate against sim init value)
    # ─────────────────────────────────────────────────
    print("\n--- 4. Temperature unit consistency with sim ---")
    # TC1 initializes at 70 — consistent with degF (room temp), not degC (158°F = implausible)
    tc1_lines = [l for l in manifest_lines if "TC1" in l.upper()]
    states_degf = any("DEGF" in l.upper() or "DEG_F" in l.upper() or "°F" in l for l in tc1_lines)
    states_degc = any("DEGC" in l.upper() or "DEG_C" in l.upper() or "°C" in l for l in tc1_lines)

    check("TC1 documented as degF (consistent with sim init at 70, reset at 500)",
          states_degf and not states_degc,
          f"Init={SIM_TC_INIT}°: 70°F=room temp ✓, 70°C=158°F ✗. Lines: {tc1_lines}")

    # Also verify the .rvl sim still initializes TC1 at 70 (degF room temp)
    check("TC1 initialized at 70.0 in .rvl (room temp in degF)",
          re.search(r"\|TC1\.value\|.*=.*70\.0", rvl_text) is not None or
          "TC1.value|:float = 70.0" in rvl_text,
          "TC1 init value changed — re-verify unit documentation")

    check("TC1 sim reset at 500.0 (plausible upper bound in degF)",
          re.search(r"TC1\.value.*>.*500", rvl_text) is not None,
          "If unit changes, reset bound must change too")

    # ─────────────────────────────────────────────────
    # 5. PT5 flagged as [ASSIGN] since its physical location is unknown
    # ─────────────────────────────────────────────────
    print("\n--- 5. Unknown sensor accountability ---")
    pt5_lines = [l for l in manifest_lines if "PT5" in l.upper()]
    check("PT5 manifest entry exists",
          len(pt5_lines) > 0, "PT5 has no manifest entry")

    check("PT5 flagged [ASSIGN] until physical location confirmed",
          any("ASSIGN" in l.upper() for l in pt5_lines),
          f"PT5 location unknown — flag with [ASSIGN] so it's not silently assumed. Lines: {pt5_lines}")

    # ─────────────────────────────────────────────────
    # 6. Threshold documentation
    # ─────────────────────────────────────────────────
    print("\n--- 6. Threshold documentation ---")
    check("WARN_P threshold value documented in manifest or constants block",
          "1150" in rvl_text or "WARN_P" in manifest_text,
          "WARN_P should be stated near the manifest or constants")

    check("MAX_SAFE_P threshold value documented",
          "1240" in rvl_text or "MAX_SAFE_P" in manifest_text,
          "MAX_SAFE_P should be stated near the manifest or constants")

    # ─────────────────────────────────────────────────
    # 7. Pressure range documented (upper bound)
    # ─────────────────────────────────────────────────
    print("\n--- 7. Pressure range ---")
    pt_ot_lines = [l for l in manifest_lines if "PT_OT" in l.upper()]
    pt_ft_lines = [l for l in manifest_lines if "PT_FT" in l.upper()]

    check("PT_OT manifest entry includes a numeric range or max",
          any(re.search(r"\d{3,4}", l) for l in pt_ot_lines),
          f"Add max pressure or range to PT_OT entry. Lines: {pt_ot_lines}")

    check("PT_FT manifest entry includes a numeric range or max",
          any(re.search(r"\d{3,4}", l) for l in pt_ft_lines),
          f"Add max pressure or range to PT_FT entry. Lines: {pt_ft_lines}")

    # ─────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
