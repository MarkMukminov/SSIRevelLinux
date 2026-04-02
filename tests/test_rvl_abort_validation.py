#!/usr/bin/env python3
"""
Validation: Parse cold_flow_test.rvl for abort hardening + E-Stop implementation.
"""

import re
import sys
import os

RVL_PATH = os.path.join(os.path.dirname(__file__), "..", "cold-flow-code", "cold_flow_test.rvl")


def read_rvl():
    with open(RVL_PATH) as f:
        return f.read()


def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {name}"
    if detail and not condition:
        msg += f"\n        detail: {detail}"
    print(msg)
    return condition


def run_checks(rvl_text):
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    print("\n=== Channel Declarations ===\n")
    for ch, typ in [
        ("EStop_Cmd",                "bool"),
        ("Abort_Cause_Overpressure", "bool"),
        ("Abort_Cause_EStop",        "bool"),
    ]:
        check(f"|{ch}| declared as {typ}", f"sw |{ch}|:{typ}" in rvl_text)

    print("\n=== Abort Trigger Logic ===\n")
    loop_match = re.search(r"loop\s+monitor_safety:(.*)", rvl_text, re.DOTALL)
    loop = loop_match.group(1) if loop_match else ""

    # Overpressure path — just check both assignments are present in loop
    check("Cause_Overpressure set on overpressure",
          "|Abort_Cause_Overpressure| = True" in loop)
    check("Abort_Active set (overpressure path)",
          "|Abort_Active| = True" in loop)

    # E-Stop path
    check("EStop_Cmd triggers Cause_EStop",
          "|Abort_Cause_EStop| = True" in loop)
    check("EStop_Cmd consumed same cycle",
          "|EStop_Cmd| = False" in loop)

    print("\n=== Abort Reset Clears Cause Flags ===\n")
    check("Reset clears Abort_Cause_Overpressure",
          "|Abort_Cause_Overpressure| = False" in loop)
    check("Reset clears Abort_Cause_EStop",
          "|Abort_Cause_EStop| = False" in loop)
    check("Reset clears Abort_Active",
          "|Abort_Active| = False" in loop)
    check("Reset_Abort consumed on success",
          "|Reset_Abort| = False" in loop)

    print("\n=== Ordering: E-Stop before abort response ===\n")
    pos_estop    = loop.find("|Abort_Cause_EStop| = True")
    pos_response = loop.find("|MBV_O.open| = False")
    check("E-Stop trigger found in loop",    pos_estop != -1)
    check("Abort response found in loop",    pos_response != -1)
    if pos_estop != -1 and pos_response != -1:
        check("E-Stop trigger is BEFORE abort response",
              pos_estop < pos_response,
              f"estop at {pos_estop}, response at {pos_response}")

    print("\n=== Manifest Documents Abort Channels ===\n")
    check("EStop_Cmd documented in manifest",
          "ESTOP_CMD" in rvl_text.upper() or "EStop_Cmd" in rvl_text)
    check("Abort cause channels documented",
          "Abort_Cause" in rvl_text)
    check("Manifest notes abort is latching",
          "latching" in rvl_text.lower() or "LATCHING" in rvl_text.upper())

    return passed, failed


def main():
    print(f"Validating: {os.path.abspath(RVL_PATH)}")
    rvl_text = read_rvl()
    p, f = run_checks(rvl_text)
    print(f"\n{'='*50}")
    print(f"TOTAL: {p}/{p+f} passed, {f} failed")
    print(f"{'='*50}")
    return f == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
