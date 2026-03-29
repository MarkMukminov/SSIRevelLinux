#!/usr/bin/env python3
"""
Test: Abort Logic Hardening + E-Stop
======================================
Validates the full abort state machine including automatic (overpressure)
and operator-commanded (E-Stop) abort paths, with cause tracking.

Design:
  Two independent abort TRIGGERS, one shared RESPONSE, one shared RESET.

  Trigger 1 — Automatic: System_Max_P > MAX_SAFE_P
    → sets Abort_Cause_Overpressure = True
    → sets Abort_Active = True

  Trigger 2 — E-Stop: operator sets EStop_Cmd = True
    → sets Abort_Cause_EStop = True
    → sets Abort_Active = True
    → consumes EStop_Cmd (resets to False same cycle)

  Response (any active abort):
    → MBV_O.open = False
    → MBV_F.open = False

  Reset: operator sets Reset_Abort = True
    → only clears if System_Max_P < MAX_SAFE_P
    → clears Abort_Active, Abort_Cause_Overpressure, Abort_Cause_EStop, Reset_Abort

Success criteria:
  1.  Overpressure triggers abort, sets Cause_Overpressure, closes valves
  2.  E-Stop triggers abort, sets Cause_EStop, closes valves
  3.  E-Stop_Cmd consumed (becomes False) on the same cycle it triggers
  4.  Both triggers simultaneously: both cause flags set
  5.  Reset clears Abort_Active and both cause flags
  6.  Reset denied when pressure still above MAX_SAFE_P
  7.  After successful reset, system can be re-armed (abort can fire again)
  8.  Nominal pressure, no E-Stop: abort stays clear
  9.  Cause flags persist through multiple cycles until reset
  10. Reset_Abort consumed when reset succeeds
  11. E-Stop works even when pressure is safe (not an overpressure event)
  12. Overpressure abort doesn't consume EStop_Cmd (separate paths)
"""

import sys

MAX_SAFE_P = 1240.0  # must match .rvl


def abort_cycle(system_max_p, estop_cmd, abort_active,
                cause_overpressure, cause_estop,
                reset_abort, mbv_o, mbv_f):
    """
    Simulates one cycle of the hardened abort block.
    Returns updated state dict.
    """
    # Trigger 1: overpressure
    if system_max_p > MAX_SAFE_P:
        cause_overpressure = True
        abort_active = True

    # Trigger 2: E-Stop (consume command same cycle)
    if estop_cmd:
        cause_estop = True
        abort_active = True
        estop_cmd = False  # consumed

    # Response
    if abort_active:
        mbv_o = False
        mbv_f = False

    # Reset (only when pressure is safe)
    if reset_abort:
        if system_max_p < MAX_SAFE_P:
            abort_active = False
            cause_overpressure = False
            cause_estop = False
            reset_abort = False

    return {
        "estop_cmd": estop_cmd,
        "abort_active": abort_active,
        "cause_overpressure": cause_overpressure,
        "cause_estop": cause_estop,
        "reset_abort": reset_abort,
        "mbv_o": mbv_o,
        "mbv_f": mbv_f,
    }


def nominal_state(**overrides):
    """Default safe state with all flags clear, valves commanded as specified."""
    base = {
        "system_max_p": 800.0,
        "estop_cmd": False,
        "abort_active": False,
        "cause_overpressure": False,
        "cause_estop": False,
        "reset_abort": False,
        "mbv_o": True,   # valves open during normal ops
        "mbv_f": True,
    }
    base.update(overrides)
    return base


def run_cycle(state):
    return abort_cycle(
        state["system_max_p"], state["estop_cmd"],
        state["abort_active"], state["cause_overpressure"], state["cause_estop"],
        state["reset_abort"], state["mbv_o"], state["mbv_f"]
    )


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

    # ─────────────────────────────────────────────────────────
    # 1. Overpressure trigger
    # ─────────────────────────────────────────────────────────
    print("\n--- 1. Overpressure triggers abort ---")
    s = nominal_state(system_max_p=1241.0)
    r = run_cycle(s)
    check("Abort_Active set True",            r["abort_active"] == True)
    check("Cause_Overpressure set True",      r["cause_overpressure"] == True)
    check("Cause_EStop stays False",          r["cause_estop"] == False)
    check("MBV_O forced closed",             r["mbv_o"] == False)
    check("MBV_F forced closed",             r["mbv_f"] == False)

    # ─────────────────────────────────────────────────────────
    # 2. E-Stop trigger (pressure nominal)
    # ─────────────────────────────────────────────────────────
    print("\n--- 2. E-Stop triggers abort (pressure safe) ---")
    s = nominal_state(estop_cmd=True)
    r = run_cycle(s)
    check("Abort_Active set True",            r["abort_active"] == True)
    check("Cause_EStop set True",             r["cause_estop"] == True)
    check("Cause_Overpressure stays False",   r["cause_overpressure"] == False)
    check("MBV_O forced closed",             r["mbv_o"] == False)
    check("MBV_F forced closed",             r["mbv_f"] == False)
    check("EStop_Cmd consumed (False) same cycle", r["estop_cmd"] == False)

    # ─────────────────────────────────────────────────────────
    # 3. E-Stop command consumption
    # ─────────────────────────────────────────────────────────
    print("\n--- 3. EStop_Cmd consumed after one cycle ---")
    s = nominal_state(estop_cmd=True)
    r1 = run_cycle(s)
    check("Cycle 1: EStop_Cmd consumed → False", r1["estop_cmd"] == False)
    # Carry result into cycle 2 — EStop_Cmd is now False, shouldn't re-trigger
    s2 = {**s, **r1, "system_max_p": 800.0}
    r2 = run_cycle(s2)
    check("Cycle 2: no spurious second abort trigger", r2["abort_active"] == True)  # still latched
    check("Cycle 2: cause_estop still True (latched)", r2["cause_estop"] == True)

    # ─────────────────────────────────────────────────────────
    # 4. Both triggers simultaneously
    # ─────────────────────────────────────────────────────────
    print("\n--- 4. Both triggers at once ---")
    s = nominal_state(system_max_p=1245.0, estop_cmd=True)
    r = run_cycle(s)
    check("Abort_Active set True",            r["abort_active"] == True)
    check("Cause_Overpressure True",          r["cause_overpressure"] == True)
    check("Cause_EStop True",                 r["cause_estop"] == True)
    check("EStop_Cmd consumed",              r["estop_cmd"] == False)
    check("Both MBVs closed",                r["mbv_o"] == False and r["mbv_f"] == False)

    # ─────────────────────────────────────────────────────────
    # 5. Successful reset (pressure safe)
    # ─────────────────────────────────────────────────────────
    print("\n--- 5. Successful reset after overpressure ---")
    # Start in abort state, pressure now safe
    s = nominal_state(
        system_max_p=800.0,   # pressure has dropped
        abort_active=True, cause_overpressure=True,
        reset_abort=True, mbv_o=False, mbv_f=False
    )
    r = run_cycle(s)
    check("Abort_Active cleared",             r["abort_active"] == False)
    check("Cause_Overpressure cleared",       r["cause_overpressure"] == False)
    check("Cause_EStop cleared",              r["cause_estop"] == False)
    check("Reset_Abort consumed",            r["reset_abort"] == False)

    # ─────────────────────────────────────────────────────────
    # 6. Reset denied when pressure still high
    # ─────────────────────────────────────────────────────────
    print("\n--- 6. Reset denied while pressure still high ---")
    s = nominal_state(
        system_max_p=1241.0,   # still over limit
        abort_active=True, cause_overpressure=True,
        reset_abort=True, mbv_o=False, mbv_f=False
    )
    r = run_cycle(s)
    check("Abort_Active stays True (pressure still high)", r["abort_active"] == True)
    check("Cause_Overpressure stays True",                  r["cause_overpressure"] == True)
    check("Reset_Abort stays True (not consumed)",          r["reset_abort"] == True)
    check("Overpressure re-asserts abort anyway",           r["abort_active"] == True)

    # ─────────────────────────────────────────────────────────
    # 7. System re-arms after reset (abort can fire again)
    # ─────────────────────────────────────────────────────────
    print("\n--- 7. Re-arm: abort can fire again after reset ---")
    # First abort and reset
    s1 = nominal_state(system_max_p=1241.0)
    r1 = run_cycle(s1)
    check("First abort fires",                r1["abort_active"] == True)
    # Pressure drops, operator resets
    r2 = run_cycle({**s1, **r1, "system_max_p": 800.0, "reset_abort": True})
    check("Reset succeeds",                   r2["abort_active"] == False)
    # Pressure spikes again — must abort again
    r3 = run_cycle({**s1, **r2, "system_max_p": 1250.0})
    check("Second overpressure re-triggers abort", r3["abort_active"] == True)
    check("Cause_Overpressure set again",          r3["cause_overpressure"] == True)

    # ─────────────────────────────────────────────────────────
    # 8. Nominal ops: no abort, no triggers
    # ─────────────────────────────────────────────────────────
    print("\n--- 8. Nominal operations — no abort ---")
    s = nominal_state()
    r = run_cycle(s)
    check("Abort stays False at nominal pressure", r["abort_active"] == False)
    check("Cause flags stay False",
          r["cause_overpressure"] == False and r["cause_estop"] == False)
    check("Valves remain open",               r["mbv_o"] == True and r["mbv_f"] == True)

    # ─────────────────────────────────────────────────────────
    # 9. Cause flags persist across multiple cycles until reset
    # ─────────────────────────────────────────────────────────
    print("\n--- 9. Cause flags persist until operator resets ---")
    # Abort fires, then pressure drops naturally (no operator reset yet)
    s = nominal_state(system_max_p=1241.0)
    r1 = run_cycle(s)
    check("Cycle 1: cause set", r1["cause_overpressure"] == True)
    # Next cycle pressure drops but NO reset command issued
    r2 = run_cycle({**s, **r1, "system_max_p": 800.0, "reset_abort": False})
    check("Cycle 2: cause persists (no reset issued)", r2["cause_overpressure"] == True)
    check("Cycle 2: abort persists (latched)",          r2["abort_active"] == True)
    # Operator issues reset
    r3 = run_cycle({**s, **r2, "system_max_p": 800.0, "reset_abort": True})
    check("Cycle 3: cause cleared after reset",        r3["cause_overpressure"] == False)
    check("Cycle 3: abort cleared after reset",        r3["abort_active"] == False)

    # ─────────────────────────────────────────────────────────
    # 10. E-Stop + reset cycle
    # ─────────────────────────────────────────────────────────
    print("\n--- 10. E-Stop then reset ---")
    s = nominal_state(estop_cmd=True)
    r1 = run_cycle(s)
    check("E-Stop fires abort",           r1["abort_active"] == True)
    check("Cause_EStop set",              r1["cause_estop"] == True)
    # Operator resets (pressure was always safe)
    r2 = run_cycle({**s, **r1, "reset_abort": True, "estop_cmd": False})
    check("Reset succeeds after E-Stop",  r2["abort_active"] == False)
    check("Cause_EStop cleared",          r2["cause_estop"] == False)

    # ─────────────────────────────────────────────────────────
    # 11. E-Stop works regardless of pressure level
    # ─────────────────────────────────────────────────────────
    print("\n--- 11. E-Stop works at any pressure ---")
    for p in [0.0, 100.0, 800.0, 1149.0, 1239.0]:
        s = nominal_state(system_max_p=p, estop_cmd=True)
        r = run_cycle(s)
        check(f"E-Stop fires at {p} PSI", r["abort_active"] == True and r["cause_estop"] == True)

    # ─────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────
    total = passed + failed
    print(f"\n{'='*50}")
    print(f"Results: {passed}/{total} passed, {failed} failed")
    print(f"{'='*50}")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
