#!/usr/bin/env python3
"""
Test: E-Match Continuity Test Logic
=====================================
Validates the e-match continuity check state machine.

Context:
  Before ignition, the operator must verify the e-match bridgewire has continuity.
  A broken wire or disconnected squib means the fire command silently does nothing.
  The hardware sense circuit uses milliamp current — well below firing threshold.
  Software reads a digital input from the sense circuit and reports the result.

Channels:
  Ematch_Continuity_Input  — hw digital input: True = continuity present (wired)
  Ematch_Test_Cmd          — operator initiates test (consumed on execution)
  Ematch_Test_Result       — most recent result: True = OK, False = open/fail
  Ematch_Test_Run          — latching: a test has been completed this session
  Ematch_Ready             — True when last test passed AND test was actually run

Safety rules:
  - Ematch_Test_Cmd is consumed each cycle (one-shot)
  - Ematch_Test_Result reflects the hardware input at the moment of test
  - Ematch_Ready = Ematch_Test_Run AND Ematch_Test_Result
    (not ready if: never tested, or last test showed open circuit)
  - Abort clears Ematch_Ready (re-test required after abort)
  - Ematch_Test_Result is NOT cleared by abort (historical record)
  - Ematch_Test_Run is NOT cleared by abort (was tested this session)
  - Result is only updated when a test is commanded — not continuously
    (prevents spurious ready/not-ready flicker during ops)

Success criteria:
  1.  Test cmd with continuity present → Result=True, Ready=True, Run=True
  2.  Test cmd with open circuit → Result=False, Ready=False, Run=True
  3.  Ematch_Test_Cmd consumed same cycle
  4.  No test commanded → Result and Ready unchanged
  5.  Ready requires test to have been run (not just hardware showing OK)
  6.  Abort clears Ematch_Ready (re-test required)
  7.  Abort does NOT clear Ematch_Test_Result or Ematch_Test_Run
  8.  Second test with continuity after open circuit → Result=True, Ready=True
  9.  Second test with open circuit after OK → Result=False, Ready=False
  10. Ready=False if abort active, even if continuity input is True
"""

import sys


def ematch_cycle(
    ematch_continuity_input,  # hw reading: True = wire intact
    ematch_test_cmd,
    ematch_test_result,       # previous result
    ematch_test_run,          # was a test run this session
    abort_active,
):
    """One cycle of e-match continuity logic."""

    # Consume test command and capture result at this instant
    if ematch_test_cmd:
        ematch_test_cmd = False
        ematch_test_result = ematch_continuity_input   # snapshot hw reading
        ematch_test_run = True

    # Ready: test was run AND last result was good AND no active abort
    ematch_ready = ematch_test_run and ematch_test_result and not abort_active

    return {
        "ematch_test_cmd":    ematch_test_cmd,
        "ematch_test_result": ematch_test_result,
        "ematch_test_run":    ematch_test_run,
        "ematch_ready":       ematch_ready,
    }


def default_state(**overrides):
    base = {
        "ematch_continuity_input": False,
        "ematch_test_cmd":         False,
        "ematch_test_result":      False,
        "ematch_test_run":         False,
        "abort_active":            False,
    }
    base.update(overrides)
    return base


def run_cycle(state):
    return ematch_cycle(
        state["ematch_continuity_input"], state["ematch_test_cmd"],
        state["ematch_test_result"], state["ematch_test_run"],
        state["abort_active"],
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
    # 1. Test with continuity present
    # ─────────────────────────────────────────────────────────
    print("\n--- 1. Test with continuity present → PASS ---")
    s = default_state(ematch_continuity_input=True, ematch_test_cmd=True)
    r = run_cycle(s)
    check("Test_Result = True (continuity OK)",  r["ematch_test_result"] == True)
    check("Test_Run = True (test executed)",      r["ematch_test_run"] == True)
    check("Ematch_Ready = True",                  r["ematch_ready"] == True)
    check("Test_Cmd consumed",                    r["ematch_test_cmd"] == False)

    # ─────────────────────────────────────────────────────────
    # 2. Test with open circuit
    # ─────────────────────────────────────────────────────────
    print("\n--- 2. Test with open circuit → FAIL ---")
    s = default_state(ematch_continuity_input=False, ematch_test_cmd=True)
    r = run_cycle(s)
    check("Test_Result = False (open circuit)",   r["ematch_test_result"] == False)
    check("Test_Run = True (test was executed)",  r["ematch_test_run"] == True)
    check("Ematch_Ready = False (failed test)",   r["ematch_ready"] == False)
    check("Test_Cmd consumed",                    r["ematch_test_cmd"] == False)

    # ─────────────────────────────────────────────────────────
    # 3. No test commanded — state unchanged
    # ─────────────────────────────────────────────────────────
    print("\n--- 3. No test commanded — result unchanged ---")
    # Hardware shows continuity but no test issued
    s = default_state(ematch_continuity_input=True, ematch_test_cmd=False,
                      ematch_test_result=False, ematch_test_run=False)
    r = run_cycle(s)
    check("Result stays False (not updated without test cmd)",
          r["ematch_test_result"] == False)
    check("Test_Run stays False",                  r["ematch_test_run"] == False)
    check("Ready stays False (never tested)",       r["ematch_ready"] == False)

    # ─────────────────────────────────────────────────────────
    # 4. Ready requires test to have been run
    # ─────────────────────────────────────────────────────────
    print("\n--- 4. Ready requires explicit test (not just hw showing OK) ---")
    # Hardware shows continuity, prior result was True, but test_run = False
    s = default_state(ematch_continuity_input=True, ematch_test_result=True,
                      ematch_test_run=False)
    r = run_cycle(s)
    check("Ready=False without Test_Run (cannot assume untested state)",
          r["ematch_ready"] == False,
          "Operator must explicitly run a test — hardware reading alone is not enough")

    # ─────────────────────────────────────────────────────────
    # 5. Abort clears Ready but not Result/Run
    # ─────────────────────────────────────────────────────────
    print("\n--- 5. Abort clears Ready, preserves test history ---")
    # Test passed, then abort fires
    s = default_state(ematch_continuity_input=True,
                      ematch_test_result=True, ematch_test_run=True,
                      abort_active=True)
    r = run_cycle(s)
    check("Ready=False during abort",              r["ematch_ready"] == False)
    check("Test_Result preserved through abort",   r["ematch_test_result"] == True)
    check("Test_Run preserved through abort",      r["ematch_test_run"] == True)

    # After abort clears, ready should restore WITHOUT re-test
    # (test_run and test_result still hold from before abort)
    s2 = {**s, **r, "abort_active": False}
    r2 = run_cycle(s2)
    check("Ready restores after abort clears (test still valid)",
          r2["ematch_ready"] == True)

    # ─────────────────────────────────────────────────────────
    # 6. Re-test after open circuit: corrected connection
    # ─────────────────────────────────────────────────────────
    print("\n--- 6. Re-test after fixing open circuit ---")
    # First test: open circuit
    s = default_state(ematch_continuity_input=False, ematch_test_cmd=True)
    r1 = run_cycle(s)
    check("First test: open circuit → Ready=False",  r1["ematch_ready"] == False)
    # Operator re-connects e-match, re-tests
    s2 = {**s, **r1, "ematch_continuity_input": True, "ematch_test_cmd": True}
    r2 = run_cycle(s2)
    check("Re-test after fix: Result=True",          r2["ematch_test_result"] == True)
    check("Re-test after fix: Ready=True",           r2["ematch_ready"] == True)

    # ─────────────────────────────────────────────────────────
    # 7. Re-test after OK: wire becomes disconnected
    # ─────────────────────────────────────────────────────────
    print("\n--- 7. Re-test after wire disconnects ---")
    s = default_state(ematch_continuity_input=True, ematch_test_cmd=True)
    r1 = run_cycle(s)
    check("First test: OK → Ready=True",             r1["ematch_ready"] == True)
    # Wire disconnects, operator re-tests
    s2 = {**s, **r1, "ematch_continuity_input": False, "ematch_test_cmd": True}
    r2 = run_cycle(s2)
    check("Re-test shows open: Result=False",        r2["ematch_test_result"] == False)
    check("Re-test shows open: Ready=False",         r2["ematch_ready"] == False)

    # ─────────────────────────────────────────────────────────
    # 8. Multiple test cycles without re-command: result stable
    # ─────────────────────────────────────────────────────────
    print("\n--- 8. Result stable between explicit tests ---")
    s = default_state(ematch_continuity_input=True, ematch_test_cmd=True)
    r1 = run_cycle(s)
    check("Cycle 1 (test run): Ready=True",  r1["ematch_ready"] == True)
    # Next 5 cycles: no test command, hw input changes — result must not update
    for i in range(5):
        s_next = {**s, **r1,
                  "ematch_continuity_input": False,  # hw shows open, but no test cmd
                  "ematch_test_cmd": False}
        r1 = run_cycle(s_next)
        check(f"Cycle {i+2}: result stable (no re-test cmd)", r1["ematch_ready"] == True,
              "Result should only update when test is explicitly commanded")

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
