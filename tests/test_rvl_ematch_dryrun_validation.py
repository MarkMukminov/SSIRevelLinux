#!/usr/bin/env python3
"""
Validation: Parse cold_flow_test.rvl for E-match continuity (Task 7)
and ignition dry run (Task 8) implementation.
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

    # ── Task 7: E-match channels ──
    print("\n=== Task 7: E-Match Channel Declarations ===\n")
    for ch in ["Ematch_Continuity_Input", "Ematch_Test_Cmd",
               "Ematch_Test_Result", "Ematch_Test_Run", "Ematch_Ready"]:
        check(f"|{ch}| declared", f"sw |{ch}|:bool" in rvl_text)

    print("\n=== Task 7: E-Match Loop Logic ===\n")
    check("ematch_continuity loop declared", "loop ematch_continuity:" in rvl_text)

    em_start = rvl_text.find("loop ematch_continuity:")
    em_end   = rvl_text.find("\nloop ", em_start + 1)
    em_loop  = rvl_text[em_start:em_end if em_end != -1 else len(rvl_text)]

    check("Test_Cmd consumed in loop",        "|Ematch_Test_Cmd| = False" in em_loop)
    check("Test_Result set from hw input",    "|Ematch_Test_Result| = |Ematch_Continuity_Input|" in em_loop)
    check("Test_Run latched True",            "|Ematch_Test_Run| = True" in em_loop)
    check("Ematch_Ready set True",            "|Ematch_Ready| = True" in em_loop)
    check("Ematch_Ready cleared (conditions not met)", "|Ematch_Ready| = False" in em_loop)
    check("Abort_Active checked for Ready",   "Abort_Active" in em_loop)

    # ── Task 8: Dry run channels ──
    print("\n=== Task 8: Dry Run Channel Declarations ===\n")
    for ch in ["Dry_Run_Active", "Dry_Run_Fire_Cmd", "Dry_Run_Passed"]:
        check(f"|{ch}| declared", f"sw |{ch}|:bool" in rvl_text)

    print("\n=== Task 8: Dry Run Logic in Ignition Loop ===\n")
    ign_start = rvl_text.find("loop ignition_sequence:")
    ign_end   = rvl_text.find("\nloop ", ign_start + 1)
    ign_loop  = rvl_text[ign_start:ign_end if ign_end != -1 else len(rvl_text)]

    check("Dry_Run_Fire_Cmd consumed",           "|Dry_Run_Fire_Cmd| = False" in ign_loop)
    check("Dry_Run_Active checked before pass",   "|Dry_Run_Active|" in ign_loop)
    check("Dry_Run_Passed set True",             "|Dry_Run_Passed| = True" in ign_loop)
    check("Dry run checks Ignition_Ready",        "Ignition_Ready" in ign_loop)

    # Critical: Ignition_Output = False must come BEFORE = True in the loop
    out_false = ign_loop.find("|Ignition_Output| = False")
    out_true  = ign_loop.find("|Ignition_Output| = True")
    check("Ignition_Output cleared before fire check",
          out_false != -1 and out_true != -1 and out_false < out_true)

    # Dry run block must NOT set Ignition_Output = True
    dry_run_block_start = ign_loop.find("|Dry_Run_Fire_Cmd| = False")
    live_fire_start     = ign_loop.find("|Ignition_Fire_Cmd| = False")
    check("Dry run block appears before live fire block",
          dry_run_block_start != -1 and live_fire_start != -1
          and dry_run_block_start < live_fire_start)

    # ── Manifest ──
    print("\n=== Manifest Documentation ===\n")
    check("E-match channels in manifest",    "Ematch_Test_Cmd" in rvl_text)
    check("Dry run channels in manifest",    "Dry_Run_Active" in rvl_text)
    check("Dry run note: identical interlocks", "identical" in rvl_text.lower() or
          "real sequence" in rvl_text.lower())

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
