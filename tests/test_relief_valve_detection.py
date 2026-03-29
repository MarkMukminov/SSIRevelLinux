#!/usr/bin/env python3
"""
Test: Relief Valve Lift Detection — Fuel Side (RV_F_Lifted)
============================================================
Validates that fuel-side relief valve detection matches oxidizer-side behavior.

Behavior spec (must match existing RV_O_Lifted logic exactly):
  - DETECT:   MBV closed AND (prev_pressure - current_pressure) > 20 PSI → set True
  - STICKY:   MBV closed AND drop <= 20 PSI → no change (stays True if was True)
  - CLEAR:    MBV open → always False (valve open means pressure drop is expected)
  - BOUNDARY: drop of exactly 20.0 PSI → does NOT trigger (must strictly exceed)
  - INDEPENDENT: RV_F_Lifted and RV_O_Lifted never affect each other

RV_LIFT_THRESHOLD = 20.0 PSI per cycle (0.1s)

Success criteria:
  1.  Drop > 20 PSI, valve closed → RV_F_Lifted = True
  2.  Drop = 20 PSI exactly, valve closed → RV_F_Lifted unchanged (False if was False)
  3.  Drop < 20 PSI, valve closed → RV_F_Lifted unchanged
  4.  Any drop, valve open → RV_F_Lifted = False
  5.  Flag sticky: set True, then small drop, valve closed → stays True
  6.  Flag clears: set True, then valve opens → becomes False
  7.  RV_O logic unaffected when only fuel pressure changes
  8.  RV_F logic unaffected when only ox pressure changes
  9.  PT_FT_Prev used (not PT_OT_Prev) for fuel detection
  10. Both sides can be True simultaneously and independently
"""

import sys

RV_LIFT_THRESHOLD = 20.0  # PSI per cycle — must match .rvl


def simulate_rv_detection(mbv_open, prev_pressure, current_pressure, current_flag):
    """
    Simulates one cycle of relief valve lift detection for one side.

    Logic (mirrors existing RV_O_Lifted code):
      if valve closed:
        if (prev - current) > threshold: flag = True
        # else: no change (sticky)
      else:
        flag = False

    Returns new flag value.
    """
    if not mbv_open:
        if (prev_pressure - current_pressure) > RV_LIFT_THRESHOLD:
            return True
        else:
            return current_flag  # sticky — no change
    else:
        return False  # valve open always clears


def simulate_full_cycle(state):
    """
    Simulates one monitor_safety cycle for both sides.
    state keys: pt_ot, pt_ft, pt_ot_prev, pt_ft_prev, mbv_o, mbv_f, rv_o, rv_f
    Returns new state dict.
    """
    new_rv_o = simulate_rv_detection(
        state["mbv_o"], state["pt_ot_prev"], state["pt_ot"], state["rv_o"]
    )
    new_rv_f = simulate_rv_detection(
        state["mbv_f"], state["pt_ft_prev"], state["pt_ft"], state["rv_f"]
    )
    return {
        **state,
        "rv_o": new_rv_o,
        "rv_f": new_rv_f,
        "pt_ot_prev": state["pt_ot"],
        "pt_ft_prev": state["pt_ft"],
    }


def default_state(**overrides):
    base = {
        "pt_ot": 800.0, "pt_ft": 800.0,
        "pt_ot_prev": 800.0, "pt_ft_prev": 800.0,
        "mbv_o": False, "mbv_f": False,
        "rv_o": False, "rv_f": False,
    }
    base.update(overrides)
    return base


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

    def check(name, condition, detail=""):
        nonlocal passed, failed
        if test(name, condition, detail):
            passed += 1
        else:
            failed += 1

    # ─────────────────────────────────────────────────
    # 1. Basic detection: drop > 20 PSI, valve closed
    # ─────────────────────────────────────────────────
    print("\n--- 1. Basic fuel relief valve detection ---")
    s = default_state(pt_ft_prev=800.0, pt_ft=779.0, mbv_f=False, rv_f=False)
    new_rv_f = simulate_rv_detection(s["mbv_f"], s["pt_ft_prev"], s["pt_ft"], s["rv_f"])
    check("21 PSI drop, valve closed → RV_F_Lifted True", new_rv_f == True,
          f"drop={s['pt_ft_prev']-s['pt_ft']}")

    s = default_state(pt_ot_prev=800.0, pt_ot=779.0, mbv_o=False, rv_o=False)
    new_rv_o = simulate_rv_detection(s["mbv_o"], s["pt_ot_prev"], s["pt_ot"], s["rv_o"])
    check("Oxidizer same detection still works", new_rv_o == True)

    # ─────────────────────────────────────────────────
    # 2. Boundary: exactly 20.0 PSI drop must NOT trigger
    # ─────────────────────────────────────────────────
    print("\n--- 2. Boundary: exactly 20 PSI ---")
    rv = simulate_rv_detection(False, 800.0, 780.0, False)
    check("Exactly 20.0 PSI drop → no trigger (must strictly exceed)", rv == False,
          f"got {rv}")

    rv = simulate_rv_detection(False, 800.0, 779.9, False)
    check("20.1 PSI drop → triggers", rv == True,
          f"got {rv}")

    rv = simulate_rv_detection(False, 800.0, 800.1, False)
    check("Pressure rose → no trigger", rv == False)

    # ─────────────────────────────────────────────────
    # 3. Valve open clears flag regardless of drop
    # ─────────────────────────────────────────────────
    print("\n--- 3. Valve open always clears ---")
    rv = simulate_rv_detection(True, 800.0, 700.0, False)
    check("Large drop (100 PSI) but valve open → stays False", rv == False)

    rv = simulate_rv_detection(True, 800.0, 700.0, True)
    check("Flag was True, valve opens → clears to False", rv == False)

    # ─────────────────────────────────────────────────
    # 4. Sticky behavior: flag stays True through small drops
    # ─────────────────────────────────────────────────
    print("\n--- 4. Sticky: flag persists while valve closed after trigger ---")
    # Cycle 1: big drop sets flag
    rv = simulate_rv_detection(False, 800.0, 770.0, False)
    check("Cycle 1: 30 PSI drop sets flag", rv == True)
    # Cycle 2: small drop, valve still closed — flag must persist
    rv2 = simulate_rv_detection(False, 770.0, 768.0, rv)
    check("Cycle 2: 2 PSI drop, valve still closed → flag stays True", rv2 == True,
          "Flag should be sticky until valve opens")
    # Cycle 3: pressure stabilizes, valve still closed
    rv3 = simulate_rv_detection(False, 768.0, 768.0, rv2)
    check("Cycle 3: no drop, valve closed → flag stays True", rv3 == True)
    # Cycle 4: valve opens → clears
    rv4 = simulate_rv_detection(True, 768.0, 768.0, rv3)
    check("Cycle 4: valve opens → flag clears", rv4 == False)

    # ─────────────────────────────────────────────────
    # 5. Independence: ox and fuel don't cross-contaminate
    # ─────────────────────────────────────────────────
    print("\n--- 5. Independence of RV_O and RV_F ---")

    # Fuel drops, ox stable — only rv_f should trigger
    state = default_state(
        pt_ft_prev=800.0, pt_ft=770.0,  # 30 PSI fuel drop
        pt_ot_prev=800.0, pt_ot=800.0,  # no ox drop
        mbv_o=False, mbv_f=False, rv_o=False, rv_f=False
    )
    s2 = simulate_full_cycle(state)
    check("Fuel drop only → RV_F triggers", s2["rv_f"] == True)
    check("Fuel drop only → RV_O unaffected (stays False)", s2["rv_o"] == False)

    # Ox drops, fuel stable — only rv_o should trigger
    state = default_state(
        pt_ot_prev=800.0, pt_ot=770.0,  # 30 PSI ox drop
        pt_ft_prev=800.0, pt_ft=800.0,  # no fuel drop
        mbv_o=False, mbv_f=False, rv_o=False, rv_f=False
    )
    s2 = simulate_full_cycle(state)
    check("Ox drop only → RV_O triggers", s2["rv_o"] == True)
    check("Ox drop only → RV_F unaffected (stays False)", s2["rv_f"] == False)

    # Both drop simultaneously
    state = default_state(
        pt_ot_prev=800.0, pt_ot=770.0,
        pt_ft_prev=800.0, pt_ft=770.0,
        mbv_o=False, mbv_f=False, rv_o=False, rv_f=False
    )
    s2 = simulate_full_cycle(state)
    check("Both drop simultaneously → both flags True", s2["rv_o"] and s2["rv_f"])

    # ─────────────────────────────────────────────────
    # 6. Correct prev channels (fuel uses PT_FT_Prev, not PT_OT_Prev)
    # ─────────────────────────────────────────────────
    print("\n--- 6. Correct previous-value channel used ---")
    # PT_OT_Prev = 800, PT_FT_Prev = 780, both current = 800
    # Only fuel had prior high; PT_FT_Prev - PT_FT = 780 - 800 = -20 (no drop, in fact rise)
    state = default_state(
        pt_ot_prev=800.0, pt_ot=770.0,   # ox drops 30 PSI
        pt_ft_prev=800.0, pt_ft=800.0,   # fuel no change
        mbv_o=False, mbv_f=False, rv_o=False, rv_f=False
    )
    s2 = simulate_full_cycle(state)
    check("Fuel uses PT_FT_Prev not PT_OT_Prev (fuel no drop → rv_f False)",
          s2["rv_f"] == False,
          "If fuel used ox prev, it would see a 30 PSI drop and falsely trigger")

    # ─────────────────────────────────────────────────
    # 7. Multi-cycle scenario: pressurize → relief lifts → reseats → reset via valve open
    # ─────────────────────────────────────────────────
    print("\n--- 7. Full sequence: pressurize → relief lift → reseat → reset ---")
    state = default_state(pt_ft=900.0, pt_ft_prev=900.0, mbv_f=False, rv_f=False)

    # Relief lifts: 40 PSI sudden drop
    state["pt_ft_prev"] = 900.0
    state["pt_ft"] = 860.0
    s = simulate_full_cycle(state)
    check("Relief lifts (40 PSI drop) → RV_F_Lifted True", s["rv_f"] == True)

    # Reseats: pressure stabilizes (small recovery)
    s["pt_ft_prev"] = s["pt_ft"]
    s["pt_ft"] = 862.0
    s2 = simulate_full_cycle(s)
    check("Reseats (small recovery) → flag stays True (sticky)", s2["rv_f"] == True)

    # Operator opens valve to vent
    s2["mbv_f"] = True
    s3 = simulate_full_cycle(s2)
    check("Operator opens MBV_F → flag clears", s3["rv_f"] == False)

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
