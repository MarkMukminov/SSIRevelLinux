#!/usr/bin/env python3
"""
Test: Ignition Dry Run / Sequence Test
========================================
Validates a dry-run mode that exercises the full ignition sequence in logic
without producing an actual hardware output on Ignition_Output.

Purpose:
  The operator can rehearse the complete pre-fire sequence — arm, ready check,
  fire command — to confirm all interlocks function, then reset and do it live.
  This is standard practice: verify the system responds correctly to every step
  before committing to an actual firing.

Design:
  Dry_Run_Active  — operator sets True to enter dry run mode
  Dry_Run_Fire_Cmd — operator-commanded fire during dry run (consumed)
  Dry_Run_Passed  — all steps exercised successfully: armed, ready, fire received

  When Dry_Run_Active is True:
    - All readiness preconditions still checked (real interlocks)
    - Dry_Run_Fire_Cmd triggers Dry_Run_Passed if ready (not Ignition_Output)
    - Ignition_Output is NEVER set True during dry run
    - Dry_Run_Fire_Cmd is consumed same cycle

  When Dry_Run_Active is False:
    - Dry_Run_Fire_Cmd has no effect
    - Dry_Run_Passed is not set

  Dry run does NOT:
    - Suppress abort logic
    - Bypass any safety interlocks
    - Affect real ignition channels

Success criteria:
  1.  Dry run fire with all preconditions met → Dry_Run_Passed=True, Output=False
  2.  Dry run fire without arm → Dry_Run_Passed=False (interlock real)
  3.  Dry run fire during abort → Dry_Run_Passed=False (abort blocks it)
  4.  Dry run fire at zero pressure → Dry_Run_Passed=False
  5.  Dry run fire at overpressure → Dry_Run_Passed=False
  6.  Dry_Run_Fire_Cmd consumed same cycle
  7.  Dry run inactive: Dry_Run_Fire_Cmd does nothing
  8.  Dry run does not set Ignition_Output under any condition
  9.  Dry_Run_Passed persists (latching) until explicitly cleared
  10. Real ignition fire cmd during dry run: Ignition_Output still fires
      (dry run mode doesn't block real fire path)
"""

import sys

MAX_SAFE_P = 1240.0


def readiness_check(ignition_armed, abort_active, system_max_p):
    """Shared readiness logic — same as live ignition."""
    return (
        ignition_armed and
        not abort_active and
        system_max_p > 0.0 and
        system_max_p < MAX_SAFE_P
    )


def dry_run_cycle(
    dry_run_active, dry_run_fire_cmd, dry_run_passed,
    ignition_armed, abort_active, system_max_p,
    ignition_fire_cmd, ignition_fired,  # real ignition channels
):
    """Simulates one cycle of dry run + real ignition logic combined."""

    ignition_ready = readiness_check(ignition_armed, abort_active, system_max_p)

    # --- Dry run path ---
    if dry_run_fire_cmd:
        dry_run_fire_cmd = False  # consumed
        if dry_run_active and ignition_ready:
            dry_run_passed = True

    # --- Real ignition path (unchanged regardless of dry run) ---
    ignition_output = False
    if ignition_fire_cmd:
        ignition_fire_cmd = False
        if ignition_ready:
            ignition_output = True
            ignition_fired = True

    return {
        "dry_run_fire_cmd":  dry_run_fire_cmd,
        "dry_run_passed":    dry_run_passed,
        "ignition_ready":    ignition_ready,
        "ignition_output":   ignition_output,
        "ignition_fire_cmd": ignition_fire_cmd,
        "ignition_fired":    ignition_fired,
    }


def default_state(**overrides):
    base = {
        "dry_run_active":    False,
        "dry_run_fire_cmd":  False,
        "dry_run_passed":    False,
        "ignition_armed":    True,
        "abort_active":      False,
        "system_max_p":      800.0,
        "ignition_fire_cmd": False,
        "ignition_fired":    False,
    }
    base.update(overrides)
    return base


def run_cycle(state):
    return dry_run_cycle(
        state["dry_run_active"], state["dry_run_fire_cmd"], state["dry_run_passed"],
        state["ignition_armed"], state["abort_active"], state["system_max_p"],
        state["ignition_fire_cmd"], state["ignition_fired"],
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
    # 1. Full nominal dry run
    # ─────────────────────────────────────────────────────────
    print("\n--- 1. Full nominal dry run sequence ---")
    s = default_state(dry_run_active=True, dry_run_fire_cmd=True)
    r = run_cycle(s)
    check("Dry_Run_Passed = True",          r["dry_run_passed"] == True)
    check("Ignition_Output = False (dry)",  r["ignition_output"] == False,
          "Dry run must NEVER trigger hardware output")
    check("Dry_Run_Fire_Cmd consumed",      r["dry_run_fire_cmd"] == False)
    check("Ignition_Ready True during dry", r["ignition_ready"] == True)

    # ─────────────────────────────────────────────────────────
    # 2. Dry run without arm → interlock enforced
    # ─────────────────────────────────────────────────────────
    print("\n--- 2. Dry run fire without arm → not passed ---")
    s = default_state(dry_run_active=True, dry_run_fire_cmd=True, ignition_armed=False)
    r = run_cycle(s)
    check("Not ready without arm",          r["ignition_ready"] == False)
    check("Dry_Run_Passed stays False",     r["dry_run_passed"] == False)
    check("Dry_Run_Fire_Cmd still consumed",r["dry_run_fire_cmd"] == False)

    # ─────────────────────────────────────────────────────────
    # 3. Dry run during abort → blocked
    # ─────────────────────────────────────────────────────────
    print("\n--- 3. Dry run fire during abort → blocked ---")
    s = default_state(dry_run_active=True, dry_run_fire_cmd=True, abort_active=True)
    r = run_cycle(s)
    check("Not ready during abort",         r["ignition_ready"] == False)
    check("Dry_Run_Passed stays False",     r["dry_run_passed"] == False)

    # ─────────────────────────────────────────────────────────
    # 4-5. Pressure interlocks
    # ─────────────────────────────────────────────────────────
    print("\n--- 4. Dry run at zero pressure → blocked ---")
    s = default_state(dry_run_active=True, dry_run_fire_cmd=True, system_max_p=0.0)
    r = run_cycle(s)
    check("Dry_Run_Passed=False at zero pressure", r["dry_run_passed"] == False)

    print("\n--- 5. Dry run at overpressure → blocked ---")
    s = default_state(dry_run_active=True, dry_run_fire_cmd=True, system_max_p=1241.0)
    r = run_cycle(s)
    check("Dry_Run_Passed=False at overpressure",  r["dry_run_passed"] == False)

    # ─────────────────────────────────────────────────────────
    # 6. Dry run inactive: Dry_Run_Fire_Cmd does nothing
    # ─────────────────────────────────────────────────────────
    print("\n--- 6. Dry run inactive → fire cmd does nothing ---")
    s = default_state(dry_run_active=False, dry_run_fire_cmd=True)
    r = run_cycle(s)
    check("Dry_Run_Passed stays False when mode inactive",
          r["dry_run_passed"] == False)
    check("Dry_Run_Fire_Cmd still consumed",
          r["dry_run_fire_cmd"] == False)

    # ─────────────────────────────────────────────────────────
    # 7. Ignition_Output NEVER fires during dry run
    # ─────────────────────────────────────────────────────────
    print("\n--- 7. Ignition_Output never fires during dry run ---")
    for armed, abort, p in [
        (True, False, 800.0),    # all good
        (True, False, 1241.0),   # overpressure
        (False, False, 800.0),   # not armed
        (True, True, 800.0),     # abort
    ]:
        s = default_state(dry_run_active=True, dry_run_fire_cmd=True,
                          ignition_armed=armed, abort_active=abort, system_max_p=p)
        r = run_cycle(s)
        check(f"No Ignition_Output (armed={armed}, abort={abort}, p={p})",
              r["ignition_output"] == False)

    # ─────────────────────────────────────────────────────────
    # 8. Dry_Run_Passed latches until cleared
    # ─────────────────────────────────────────────────────────
    print("\n--- 8. Dry_Run_Passed latches ---")
    s = default_state(dry_run_active=True, dry_run_fire_cmd=True)
    r1 = run_cycle(s)
    check("Dry run passes", r1["dry_run_passed"] == True)
    # Next cycle, no command — should stay True
    s2 = {**s, **r1, "dry_run_fire_cmd": False}
    r2 = run_cycle(s2)
    check("Dry_Run_Passed persists next cycle",  r2["dry_run_passed"] == True)

    # ─────────────────────────────────────────────────────────
    # 9. Real fire cmd during dry run still works
    # ─────────────────────────────────────────────────────────
    print("\n--- 9. Real fire cmd during dry run mode → still fires ---")
    s = default_state(dry_run_active=True, ignition_fire_cmd=True)
    r = run_cycle(s)
    check("Real Ignition_Output fires even in dry run mode",
          r["ignition_output"] == True,
          "Dry run mode does not block the real fire path")
    check("Ignition_Fired latches",             r["ignition_fired"] == True)
    check("Dry_Run_Passed not set by real cmd", r["dry_run_passed"] == False)

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
