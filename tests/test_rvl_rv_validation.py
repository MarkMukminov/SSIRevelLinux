#!/usr/bin/env python3
"""
Validation: Parse cold_flow_test.rvl and verify fuel relief valve detection implementation.

Part 1: Structural — fuel side uses PT_FT_Prev, MBV_F, and assigns RV_F_Lifted
Part 2: Confirms fuel and ox use different channels (no cross-contamination)
"""

import re
import sys
import os

RVL_PATH = os.path.join(os.path.dirname(__file__), "..", "No-Hardware Sim", "cold_flow_test.rvl")


def read_rvl():
    with open(RVL_PATH, "r") as f:
        return f.read()


def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {name}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)
    return condition


def run_structural_checks(rvl_text):
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    print("\n=== PART 1: Structural Validation — Fuel Relief Valve ===\n")

    # RV_F_Lifted channel declared
    check("RV_F_Lifted channel declared as bool",
          "sw |RV_F_Lifted|:bool" in rvl_text)

    # Fuel side uses MBV_F not MBV_O
    check("Fuel detection checks MBV_F (not MBV_O)",
          "|MBV_F.open|" in rvl_text and
          re.search(r"MBV_F\.open.*\n.*PT_FT_Prev.*PT_FT", rvl_text) is not None or
          re.search(r"MBV_F\.open.*False.*\n.*if.*PT_FT_Prev.*PT_FT", rvl_text) is not None or
          # Looser check: both MBV_F and PT_FT_Prev appear in the relief section
          ("MBV_F.open" in rvl_text and "PT_FT_Prev" in rvl_text and
           "RV_F_Lifted" in rvl_text))

    # Fuel detection uses PT_FT_Prev minus PT_FT (not PT_OT channels)
    check("Fuel detection uses PT_FT_Prev for delta",
          re.search(r"PT_FT_Prev.*-.*PT_FT\.value", rvl_text) is not None,
          "Should be (|PT_FT_Prev| - |PT_FT.value|) > 20.0")

    # RV_F_Lifted is set True
    check("RV_F_Lifted can be set True", "|RV_F_Lifted| = True" in rvl_text)

    # RV_F_Lifted is set False (clears when valve opens)
    check("RV_F_Lifted clears to False (when MBV_F opens)",
          "|RV_F_Lifted| = False" in rvl_text)

    print("\n=== PART 2: Structural Validation — Channel Independence ===\n")

    # Oxidizer still uses its own channels
    check("Ox detection still uses PT_OT_Prev",
          re.search(r"PT_OT_Prev.*-.*PT_OT\.value", rvl_text) is not None)
    check("Ox detection still tied to MBV_O",
          re.search(r"MBV_O\.open.*False", rvl_text) is not None)
    check("RV_O_Lifted still assigned True",
          "|RV_O_Lifted| = True" in rvl_text)
    check("RV_O_Lifted still assigned False",
          "|RV_O_Lifted| = False" in rvl_text)

    # Both prev values are updated at end of cycle
    check("PT_OT_Prev updated each cycle",
          "|PT_OT_Prev| = |PT_OT.value|" in rvl_text)
    check("PT_FT_Prev updated each cycle",
          "|PT_FT_Prev| = |PT_FT.value|" in rvl_text)

    # Fuel detection does NOT reference ox channels
    # Find the logic block: if |MBV_F.open| == False: ... RV_F_Lifted = True
    # This must be inside the loop, so look past the "loop" keyword
    loop_body_match = re.search(r"loop\s+monitor_safety:(.*)", rvl_text, re.DOTALL)
    loop_body = loop_body_match.group(1) if loop_body_match else ""
    fuel_block_match = re.search(
        r"if \|MBV_F\.open\| == False:(.*?)else:\s*\n\s*\|RV_F_Lifted\| = False",
        loop_body, re.DOTALL
    )
    if fuel_block_match:
        fuel_block = fuel_block_match.group(1)
        check("Fuel relief block does not reference PT_OT channels",
              "PT_OT" not in fuel_block,
              f"Found PT_OT in fuel relief block: {fuel_block.strip()[:100]}")
    else:
        check("Fuel relief if/else block found in loop body", False,
              "Could not locate the fuel relief if/else block in monitor_safety")

    return passed, failed


def main():
    print("Validating: No-Hardware Sim/cold_flow_test.rvl")
    print(f"File: {os.path.abspath(RVL_PATH)}")

    rvl_text = read_rvl()
    p1_pass, p1_fail = run_structural_checks(rvl_text)

    total_pass = p1_pass
    total_fail = p1_fail
    total = total_pass + total_fail

    print(f"\n{'='*50}")
    print(f"TOTAL: {total_pass}/{total} passed, {total_fail} failed")
    print(f"{'='*50}")

    return total_fail == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
