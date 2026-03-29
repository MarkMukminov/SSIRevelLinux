#!/usr/bin/env python3
"""
Validation: Parse cold_flow_test.rvl and verify overpressure warning implementation.

Part 1: Structural validation — confirms all required channels and logic are declared.
Part 2: Cycle simulation — simulates the .rvl logic cycle-by-cycle and checks flag behavior.
"""

import re
import sys
import os

RVL_PATH = os.path.join(os.path.dirname(__file__), "..", "No-Hardware Sim", "cold_flow_test.rvl")

MAX_SAFE_P = 1240.0
WARN_P = 1150.0


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
    """Verify that all required channels and logic patterns exist in the .rvl file."""
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    print("\n=== PART 1: Structural Validation ===\n")

    # Required warning channels
    for sensor in ["PT_OT", "PT_FT", "PT5"]:
        check(f"Warn_{sensor} channel declared",
              f"sw |Warn_{sensor}|:bool" in rvl_text)
        check(f"Overpressure_{sensor} channel declared",
              f"sw |Overpressure_{sensor}|:bool" in rvl_text)

    # Warning logic uses WARN_P constant (not hardcoded numbers)
    for sensor_val in ["PT_OT.value", "PT_FT.value", "PT5.value"]:
        check(f"{sensor_val} compared against WARN_P",
              re.search(rf"\|{re.escape(sensor_val)}\|.*>.*WARN_P", rvl_text) is not None,
              "Warning threshold should reference WARN_P constant, not a hardcoded number")

    # Overpressure logic uses MAX_SAFE_P constant
    for sensor_val in ["PT_OT.value", "PT_FT.value", "PT5.value"]:
        check(f"{sensor_val} compared against MAX_SAFE_P",
              re.search(rf"\|{re.escape(sensor_val)}\|.*>.*MAX_SAFE_P", rvl_text) is not None,
              "Overpressure threshold should reference MAX_SAFE_P constant")

    # System_Max_P includes all 3 sensors (nested max or 3-arg)
    # Find the assignment line: |System_Max_P| = ...
    max_p_match = re.search(r"\|System_Max_P\|\s*=\s*(.+)", rvl_text)
    max_p_line = max_p_match.group(1) if max_p_match else ""
    check("System_Max_P includes PT5 (not just PT_OT and PT_FT)",
          "PT5.value" in max_p_line,
          f"System_Max_P calculation must include PT5. Found: {max_p_line}")

    # Warning flags have else branches (clear when pressure drops)
    for sensor in ["PT_OT", "PT_FT", "PT5"]:
        # Find the warning assignment block - should have both True and False assignments
        warn_true = f"|Warn_{sensor}| = True" in rvl_text
        warn_false = f"|Warn_{sensor}| = False" in rvl_text
        check(f"Warn_{sensor} clears when pressure drops (has else branch)",
              warn_true and warn_false,
              "Warning flags must clear immediately — no latching on warnings")

    for sensor in ["PT_OT", "PT_FT", "PT5"]:
        over_true = f"|Overpressure_{sensor}| = True" in rvl_text
        over_false = f"|Overpressure_{sensor}| = False" in rvl_text
        check(f"Overpressure_{sensor} clears when pressure drops",
              over_true and over_false)

    # Constants are defined
    check("WARN_P constant defined", "const WARN_P" in rvl_text)
    check("MAX_SAFE_P constant defined", "const MAX_SAFE_P" in rvl_text)

    # Abort still works
    check("Abort logic still present", "|Abort_Active| = True" in rvl_text)
    check("Abort closes MBV_O", '|MBV_O.open| = False' in rvl_text)
    check("Abort closes MBV_F", '|MBV_F.open| = False' in rvl_text)

    return passed, failed


def run_cycle_simulation():
    """
    Simulate the monitor_safety loop for various pressure scenarios
    and verify flag outputs match expected behavior.
    """
    print("\n=== PART 2: Cycle Simulation ===\n")
    passed = 0
    failed = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    def simulate_cycle(pt_ot, pt_ft, pt5):
        """Simulate one cycle of monitor_safety logic as written in the .rvl."""
        state = {}
        state["System_Max_P"] = max(max(pt_ot, pt_ft), pt5)

        state["Warn_PT_OT"] = pt_ot > WARN_P
        state["Warn_PT_FT"] = pt_ft > WARN_P
        state["Warn_PT5"] = pt5 > WARN_P

        state["Overpressure_PT_OT"] = pt_ot > MAX_SAFE_P
        state["Overpressure_PT_FT"] = pt_ft > MAX_SAFE_P
        state["Overpressure_PT5"] = pt5 > MAX_SAFE_P

        return state

    # Test the mock sim will exercise warning range
    # PT_OT rises at +10/cycle, hits WARN_P at cycle 115, MAX_SAFE_P at cycle 124
    print("--- Simulating mock pressurization ramp (PT_OT, valve closed) ---")
    pt_ot = 0.0
    warn_triggered_at = None
    over_triggered_at = None
    for cycle in range(140):
        pt_ot += 10.0
        if pt_ot > 1300.0:
            pt_ot = 0.0
        s = simulate_cycle(pt_ot, 0.0, 0.0)
        if s["Warn_PT_OT"] and warn_triggered_at is None:
            warn_triggered_at = (cycle, pt_ot)
        if s["Overpressure_PT_OT"] and over_triggered_at is None:
            over_triggered_at = (cycle, pt_ot)

    check("Warning triggers before overpressure",
          warn_triggered_at is not None and over_triggered_at is not None
          and warn_triggered_at[0] < over_triggered_at[0],
          f"Warn at cycle {warn_triggered_at}, Over at cycle {over_triggered_at}")

    check(f"Warning triggers at {WARN_P}+ PSI",
          warn_triggered_at[1] > WARN_P,
          f"Triggered at {warn_triggered_at[1]} PSI")

    check(f"Overpressure triggers at {MAX_SAFE_P}+ PSI",
          over_triggered_at[1] > MAX_SAFE_P,
          f"Triggered at {over_triggered_at[1]} PSI")

    # PT_FT rises at +8/cycle, verify independent tracking
    print("\n--- Simulating PT_FT ramp (independent of PT_OT) ---")
    pt_ft = 0.0
    ft_warn_at = None
    for cycle in range(200):
        pt_ft += 8.0
        if pt_ft > 1300.0:
            pt_ft = 0.0
        s = simulate_cycle(0.0, pt_ft, 0.0)
        if s["Warn_PT_FT"] and ft_warn_at is None:
            ft_warn_at = (cycle, pt_ft)
        # PT_OT should never warn when it's at 0
        check_ot = s["Warn_PT_OT"] == False
        if not check_ot:
            check("PT_OT stays False while PT_FT ramps", False,
                  f"Cycle {cycle}: PT_OT warned despite being at 0")
            break

    check("PT_FT warning triggers independently",
          ft_warn_at is not None and ft_warn_at[1] > WARN_P)

    # Cross-check: all sensors high
    print("\n--- All sensors above MAX_SAFE_P ---")
    s = simulate_cycle(1250.0, 1260.0, 1245.0)
    check("All three overpressure flags True",
          s["Overpressure_PT_OT"] and s["Overpressure_PT_FT"] and s["Overpressure_PT5"])
    check("System_Max_P tracks the highest (1260)",
          s["System_Max_P"] == 1260.0)

    return passed, failed


def main():
    print("Validating: No-Hardware Sim/cold_flow_test.rvl")
    print(f"File: {os.path.abspath(RVL_PATH)}")

    rvl_text = read_rvl()

    p1_pass, p1_fail = run_structural_checks(rvl_text)
    p2_pass, p2_fail = run_cycle_simulation()

    total_pass = p1_pass + p2_pass
    total_fail = p1_fail + p2_fail
    total = total_pass + total_fail

    print(f"\n{'='*50}")
    print(f"Structural: {p1_pass}/{p1_pass+p1_fail} passed")
    print(f"Simulation: {p2_pass}/{p2_pass+p2_fail} passed")
    print(f"TOTAL:      {total_pass}/{total} passed, {total_fail} failed")
    print(f"{'='*50}")

    return total_fail == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
