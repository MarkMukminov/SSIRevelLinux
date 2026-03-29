#!/usr/bin/env python3
"""
Validation: Parse cold_flow_test.rvl for valve state tracking implementation.

Checks:
  1. Channel declarations exist for cmd_prev and cmd_change for both valves
  2. Transition detection block exists in the loop and uses != comparison
  3. Transition detection comes BEFORE the abort enforcement block
  4. cmd_prev update comes AFTER the abort enforcement block
  5. Manifest documents valves as COMMANDED (not confirmed)
"""

import re
import sys
import os

RVL_PATH = os.path.join(os.path.dirname(__file__), "..", "No-Hardware Sim", "cold_flow_test.rvl")


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
    for ch in ["MBV_O.cmd_prev", "MBV_F.cmd_prev", "MBV_O.cmd_change", "MBV_F.cmd_change"]:
        check(f"|{ch}| declared as bool",
              f"sw |{ch}|:bool" in rvl_text)

    print("\n=== Transition Detection Logic ===\n")
    # Uses != comparison for change detection
    check("MBV_O transition uses != comparison",
          re.search(r"MBV_O\.open.*!=.*MBV_O\.cmd_prev", rvl_text) is not None)
    check("MBV_F transition uses != comparison",
          re.search(r"MBV_F\.open.*!=.*MBV_F\.cmd_prev", rvl_text) is not None)
    check("MBV_O.cmd_change set True on transition",
          "|MBV_O.cmd_change| = True" in rvl_text)
    check("MBV_F.cmd_change set True on transition",
          "|MBV_F.cmd_change| = True" in rvl_text)
    check("MBV_O.cmd_change cleared False when no transition",
          "|MBV_O.cmd_change| = False" in rvl_text)
    check("MBV_F.cmd_change cleared False when no transition",
          "|MBV_F.cmd_change| = False" in rvl_text)

    print("\n=== Ordering: detection before abort, cmd_prev after abort ===\n")
    loop_match = re.search(r"loop\s+monitor_safety:(.*)", rvl_text, re.DOTALL)
    loop_body = loop_match.group(1) if loop_match else ""

    pos_change_o  = loop_body.find("MBV_O.cmd_change| = True")
    pos_abort_set = loop_body.find("|Abort_Active| = True")
    pos_abort_enf = loop_body.find("|MBV_O.open| = False")  # abort enforcement line
    pos_prev_o    = loop_body.rfind("|MBV_O.cmd_prev| = |MBV_O.open|")  # last occurrence

    check("Transition detection found in loop body", pos_change_o != -1)
    check("Abort enforcement found in loop body",    pos_abort_enf != -1)
    check("cmd_prev update found in loop body",      pos_prev_o != -1)

    if pos_change_o != -1 and pos_abort_enf != -1:
        check("Transition detection is BEFORE abort enforcement",
              pos_change_o < pos_abort_enf,
              f"change_o at {pos_change_o}, abort_enf at {pos_abort_enf}")

    if pos_abort_enf != -1 and pos_prev_o != -1:
        check("cmd_prev update is AFTER abort enforcement",
              pos_prev_o > pos_abort_enf,
              f"prev_o at {pos_prev_o}, abort_enf at {pos_abort_enf}")

    print("\n=== Manifest documents COMMANDED warning ===\n")
    check("Manifest contains 'COMMANDED' for valve channels",
          "COMMANDED" in rvl_text.upper() and "MBV_O" in rvl_text)
    check("Manifest or comment warns no position feedback",
          "NO POSITION FEEDBACK" in rvl_text.upper() or
          "NO FEEDBACK" in rvl_text.upper() or
          "COMMANDED POSITION ONLY" in rvl_text.upper() or
          "COMMANDED position only" in rvl_text)

    return passed, failed


def main():
    print(f"Validating: {os.path.abspath(RVL_PATH)}")
    rvl_text = read_rvl()
    p, f = run_checks(rvl_text)
    total = p + f
    print(f"\n{'='*50}")
    print(f"TOTAL: {p}/{total} passed, {f} failed")
    print(f"{'='*50}")
    return f == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
