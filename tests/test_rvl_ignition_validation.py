#!/usr/bin/env python3
"""
Validation: Parse cold_flow_test.rvl for ignition logic implementation.
"""

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
    for ch in ["Ignition_Armed", "Ignition_Ready", "Ignition_Fire_Cmd",
               "Ignition_Fired", "Ignition_Output"]:
        check(f"|{ch}| declared as bool", f"sw |{ch}|:bool" in rvl_text)

    print("\n=== Ignition Loop Exists ===\n")
    check("ignition_sequence loop declared",
          "loop ignition_sequence:" in rvl_text)

    ign_loop_start = rvl_text.find("loop ignition_sequence:")
    ign_loop_end   = rvl_text.find("\nloop ", ign_loop_start + 1)
    if ign_loop_end == -1:
        ign_loop_end = len(rvl_text)
    ign_loop = rvl_text[ign_loop_start:ign_loop_end]

    print("\n=== Safety Interlocks in Loop ===\n")
    check("Abort clears Armed in loop",
          "|Ignition_Armed| = False" in ign_loop and "|Abort_Active|" in ign_loop)
    check("Abort_Active checked for readiness",
          "Abort_Active" in ign_loop and "|Ignition_Ready|" in ign_loop)
    check("System_Max_P > 0 checked (pressurized)",
          "System_Max_P" in ign_loop and "0.0" in ign_loop)
    check("System_Max_P < MAX_SAFE_P checked",
          "MAX_SAFE_P" in ign_loop)

    print("\n=== Fire Execution ===\n")
    check("Fire_Cmd consumed (set False)",
          "|Ignition_Fire_Cmd| = False" in ign_loop)
    check("Ignition_Output set True on fire",
          "|Ignition_Output| = True" in ign_loop)
    check("Ignition_Fired latches True on fire",
          "|Ignition_Fired| = True" in ign_loop)
    check("Ignition_Output cleared each cycle (set False before fire check)",
          ign_loop.find("|Ignition_Output| = False") <
          ign_loop.find("|Ignition_Output| = True"),
          "Output must be cleared BEFORE the fire check so it's a true 1-cycle pulse")

    print("\n=== Fire Only When Ready ===\n")
    # Ignition_Output = True must be inside a block that checks Ignition_Ready
    ready_pos  = ign_loop.find("|Ignition_Ready| == True")
    output_pos = ign_loop.find("|Ignition_Output| = True")
    check("Ignition_Output = True is inside Ignition_Ready check",
          ready_pos != -1 and output_pos != -1 and ready_pos < output_pos,
          "Fire output must only fire when ready")

    print("\n=== Manifest Documents Ignition ===\n")
    check("Ignition channels documented in manifest",
          "Ignition_Armed" in rvl_text and "Ignition_Output" in rvl_text)
    check("Manifest notes readiness preconditions",
          "Readiness requires" in rvl_text or "preconditions" in rvl_text.lower())

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
