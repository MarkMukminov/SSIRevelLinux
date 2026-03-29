#!/usr/bin/env python3
"""
Test: Graduated Overpressure Warning Logic
==========================================
Validates that per-sensor warning and overpressure flags behave correctly.

Success criteria:
1. Below WARN_P (1150): all warning flags False, all overpressure flags False
2. Between WARN_P and MAX_SAFE_P (1150-1240): warning flag True, overpressure False
3. Above MAX_SAFE_P (1240): both warning and overpressure True
4. Each sensor is independent — PT_OT high does not affect PT_FT flags
5. Abort triggers when ANY sensor exceeds MAX_SAFE_P
6. Abort does NOT trigger on warning alone
7. Flags clear immediately when pressure drops (no latching on warnings)
"""

import sys

# --- Constants (must match .rvl file) ---
MAX_SAFE_P = 1240.0
WARN_P = 1150.0


def compute_warnings(pt_ot, pt_ft, pt5):
    """
    Simulates the per-sensor warning logic that the .rvl code should implement.
    Returns dict of all flag states.
    """
    warn_pt_ot = pt_ot > WARN_P
    warn_pt_ft = pt_ft > WARN_P
    warn_pt5 = pt5 > WARN_P

    over_pt_ot = pt_ot > MAX_SAFE_P
    over_pt_ft = pt_ft > MAX_SAFE_P
    over_pt5 = pt5 > MAX_SAFE_P

    system_max_p = max(pt_ot, pt_ft, pt5)

    # Abort triggers on ANY overpressure (this is latching in the real system,
    # but the FLAG detection itself is instantaneous)
    any_overpressure = over_pt_ot or over_pt_ft or over_pt5

    return {
        "Warn_PT_OT": warn_pt_ot,
        "Warn_PT_FT": warn_pt_ft,
        "Warn_PT5": warn_pt5,
        "Overpressure_PT_OT": over_pt_ot,
        "Overpressure_PT_FT": over_pt_ft,
        "Overpressure_PT5": over_pt5,
        "System_Max_P": system_max_p,
        "any_overpressure": any_overpressure,
    }


def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    msg = f"  [{status}] {name}"
    if detail and not condition:
        msg += f" — {detail}"
    print(msg)
    return condition


def run_tests():
    passed = 0
    failed = 0
    total = 0

    def check(name, condition, detail=""):
        nonlocal passed, failed, total
        total += 1
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    # =====================================================
    # Scenario 1: All pressures nominal (well below WARN_P)
    # =====================================================
    print("\n--- Scenario 1: All pressures nominal (500 PSI) ---")
    r = compute_warnings(500.0, 500.0, 500.0)
    check("PT_OT warning is False", r["Warn_PT_OT"] == False)
    check("PT_FT warning is False", r["Warn_PT_FT"] == False)
    check("PT5 warning is False", r["Warn_PT5"] == False)
    check("PT_OT overpressure is False", r["Overpressure_PT_OT"] == False)
    check("PT_FT overpressure is False", r["Overpressure_PT_FT"] == False)
    check("PT5 overpressure is False", r["Overpressure_PT5"] == False)
    check("No overpressure condition", r["any_overpressure"] == False)
    check("System_Max_P is 500", r["System_Max_P"] == 500.0)

    # =====================================================
    # Scenario 2: One sensor in warning range, others nominal
    # =====================================================
    print("\n--- Scenario 2: PT_OT at 1200 (warning), others at 500 ---")
    r = compute_warnings(1200.0, 500.0, 500.0)
    check("PT_OT warning is True", r["Warn_PT_OT"] == True)
    check("PT_FT warning is False (independent)", r["Warn_PT_FT"] == False)
    check("PT5 warning is False (independent)", r["Warn_PT5"] == False)
    check("PT_OT overpressure is False (below MAX)", r["Overpressure_PT_OT"] == False)
    check("No overpressure condition", r["any_overpressure"] == False)
    check("System_Max_P is 1200", r["System_Max_P"] == 1200.0)

    # =====================================================
    # Scenario 3: One sensor overpressure
    # =====================================================
    print("\n--- Scenario 3: PT_FT at 1250 (overpressure), others at 800 ---")
    r = compute_warnings(800.0, 1250.0, 800.0)
    check("PT_OT warning is False", r["Warn_PT_OT"] == False)
    check("PT_FT warning is True", r["Warn_PT_FT"] == True)
    check("PT_FT overpressure is True", r["Overpressure_PT_FT"] == True)
    check("PT_OT overpressure is False (independent)", r["Overpressure_PT_OT"] == False)
    check("Overpressure condition detected", r["any_overpressure"] == True)

    # =====================================================
    # Scenario 4: Exactly at thresholds (boundary)
    # =====================================================
    print("\n--- Scenario 4: Boundary conditions ---")
    r = compute_warnings(WARN_P, WARN_P, WARN_P)
    check("At exactly WARN_P: warning is False (must EXCEED)", r["Warn_PT_OT"] == False,
          f"Got {r['Warn_PT_OT']} at exactly {WARN_P}")

    r = compute_warnings(MAX_SAFE_P, MAX_SAFE_P, MAX_SAFE_P)
    check("At exactly MAX_SAFE_P: overpressure is False (must EXCEED)", r["Overpressure_PT_OT"] == False,
          f"Got {r['Overpressure_PT_OT']} at exactly {MAX_SAFE_P}")

    r = compute_warnings(WARN_P + 0.1, 0.0, 0.0)
    check("Just above WARN_P: warning is True", r["Warn_PT_OT"] == True)

    r = compute_warnings(MAX_SAFE_P + 0.1, 0.0, 0.0)
    check("Just above MAX_SAFE_P: overpressure is True", r["Overpressure_PT_OT"] == True)

    # =====================================================
    # Scenario 5: Warnings clear when pressure drops
    # =====================================================
    print("\n--- Scenario 5: Warning flags clear when pressure drops ---")
    # First cycle: high pressure
    r1 = compute_warnings(1200.0, 500.0, 500.0)
    check("High pressure: warning active", r1["Warn_PT_OT"] == True)
    # Next cycle: pressure dropped
    r2 = compute_warnings(900.0, 500.0, 500.0)
    check("Dropped pressure: warning cleared", r2["Warn_PT_OT"] == False)

    # =====================================================
    # Scenario 6: Multiple sensors in different states
    # =====================================================
    print("\n--- Scenario 6: Mixed states across sensors ---")
    r = compute_warnings(1200.0, 1250.0, 500.0)
    check("PT_OT in warning range", r["Warn_PT_OT"] == True and r["Overpressure_PT_OT"] == False)
    check("PT_FT in overpressure", r["Warn_PT_FT"] == True and r["Overpressure_PT_FT"] == True)
    check("PT5 nominal", r["Warn_PT5"] == False and r["Overpressure_PT5"] == False)
    check("System detects overpressure", r["any_overpressure"] == True)
    check("System_Max_P tracks highest", r["System_Max_P"] == 1250.0)

    # =====================================================
    # Scenario 7: All at zero
    # =====================================================
    print("\n--- Scenario 7: All at zero ---")
    r = compute_warnings(0.0, 0.0, 0.0)
    check("No warnings at zero",
          not any([r["Warn_PT_OT"], r["Warn_PT_FT"], r["Warn_PT5"]]))
    check("No overpressure at zero",
          not any([r["Overpressure_PT_OT"], r["Overpressure_PT_FT"], r["Overpressure_PT5"]]))

    # =====================================================
    # Summary
    # =====================================================
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
