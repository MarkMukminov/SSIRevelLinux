#!/usr/bin/env python3
"""
Test: Valve State Tracking
===========================
Validates valve commanded-position transition detection.

Context:
  MBV_O.open and MBV_F.open are COMMANDED states — no position feedback
  exists in the current hardware config. We must never claim the valve IS
  open/closed, only that it was COMMANDED open/closed.

What we track:
  - cmd_prev: previous cycle's commanded state (internal, drives transition logic)
  - cmd_change: True for exactly ONE cycle whenever commanded state transitions
                (either open→closed or closed→open)

Ordering contract:
  Transition detection runs BEFORE the abort enforcement block.
  This means:
    - Operator-issued commands generate a cmd_change pulse on the cycle issued.
    - Abort-forced closures do NOT generate a cmd_change pulse (the
      Abort_Active flag already tells the operator why the valve closed).
  cmd_prev is updated AFTER abort enforcement so it captures the post-abort
  state and the next cycle sees no spurious transition.

Success criteria:
  1.  closed→open transition:   cmd_change = True for exactly 1 cycle
  2.  open→closed transition:   cmd_change = True for exactly 1 cycle
  3.  Stable open, N cycles:    cmd_change = False every cycle
  4.  Stable closed, N cycles:  cmd_change = False every cycle
  5.  Double transition in 2 cycles: each gets its own 1-cycle pulse
  6.  MBV_O and MBV_F transitions are fully independent
  7.  Abort-forced close does NOT generate cmd_change (abort active = explanation)
  8.  cmd_prev updates correctly so no spurious pulse on cycle after transition
"""

import sys

# ---------- reference implementation of the valve tracking logic ----------

def valve_tracking_cycle(mbv_open, cmd_prev_in, abort_active):
    """
    Simulates one loop cycle for valve state tracking.

    Ordering (matches .rvl loop):
      1. Detect transition using current mbv_open vs cmd_prev_in
      2. If abort active: force mbv_open = False
      3. Update cmd_prev = post-abort mbv_open

    Returns (cmd_change, new_cmd_prev, new_mbv_open)
    """
    # Step 1: detect transition BEFORE abort can change anything
    cmd_change = (mbv_open != cmd_prev_in)

    # Step 2: abort enforcement (AFTER transition detection)
    if abort_active:
        mbv_open = False

    # Step 3: capture final state for next cycle
    new_cmd_prev = mbv_open

    return cmd_change, new_cmd_prev, mbv_open


def simulate_sequence(events):
    """
    Run a sequence of valve events through the tracking logic.
    events: list of (mbv_open, abort_active) tuples per cycle
    Returns list of (cmd_change, cmd_prev, mbv_open) per cycle.
    """
    cmd_prev = False
    results = []
    for mbv_open, abort_active in events:
        change, cmd_prev, mbv_open = valve_tracking_cycle(mbv_open, cmd_prev, abort_active)
        results.append((change, cmd_prev, mbv_open))
    return results


# ---------- test helpers ----------

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
    # 1. closed → open transition
    # ─────────────────────────────────────────────────────────
    print("\n--- 1. closed → open transition ---")
    results = simulate_sequence([
        (False, False),   # cycle 0: stable closed
        (True,  False),   # cycle 1: operator commands open
        (True,  False),   # cycle 2: stable open
        (True,  False),   # cycle 3: stable open
    ])
    check("Cycle 0 (stable closed): no change",        results[0][0] == False)
    check("Cycle 1 (open command): cmd_change = True", results[1][0] == True)
    check("Cycle 2 (stable open): cmd_change = False", results[2][0] == False)
    check("Cycle 3 (stable open): cmd_change = False", results[3][0] == False)

    # ─────────────────────────────────────────────────────────
    # 2. open → closed transition
    # ─────────────────────────────────────────────────────────
    print("\n--- 2. open → closed transition ---")
    # Pre-warm: one cycle to establish cmd_prev=True before the test scenario
    results = simulate_sequence([
        (True,  False),   # warm-up: establish valve open in prev state
        (True,  False),   # cycle 0: stable open (cmd_prev now matches)
        (False, False),   # cycle 1: operator commands closed
        (False, False),   # cycle 2: stable closed
    ])
    results = results[1:]  # drop warm-up cycle
    check("Cycle 0 (stable open): no change",           results[0][0] == False)
    check("Cycle 1 (close command): cmd_change = True", results[1][0] == True)
    check("Cycle 2 (stable closed): cmd_change = False",results[2][0] == False)

    # ─────────────────────────────────────────────────────────
    # 3. Stable states generate no pulses
    # ─────────────────────────────────────────────────────────
    print("\n--- 3. Stable state — no spurious pulses ---")
    results = simulate_sequence([(False, False)] * 10)
    check("10 cycles stable closed: zero cmd_change pulses",
          all(r[0] == False for r in results),
          str([r[0] for r in results]))

    # Pre-warm to establish cmd_prev=True before the 10-cycle stable test
    results = simulate_sequence([(True, False)] * 11)
    results = results[1:]  # drop warm-up cycle
    check("10 cycles stable open: zero cmd_change pulses",
          all(r[0] == False for r in results),
          str([r[0] for r in results]))

    # ─────────────────────────────────────────────────────────
    # 4. Rapid toggle: each transition gets exactly one pulse
    # ─────────────────────────────────────────────────────────
    print("\n--- 4. Rapid toggle — each transition one pulse ---")
    results = simulate_sequence([
        (False, False),   # 0: closed
        (True,  False),   # 1: open   → pulse
        (False, False),   # 2: closed → pulse
        (True,  False),   # 3: open   → pulse
        (False, False),   # 4: closed → pulse
    ])
    pulses = [r[0] for r in results]
    check("Rapid toggle: pulse pattern is [F,T,T,T,T]",
          pulses == [False, True, True, True, True],
          f"Got: {pulses}")

    # ─────────────────────────────────────────────────────────
    # 5. Independence: O and F transitions don't cross
    # ─────────────────────────────────────────────────────────
    print("\n--- 5. Independence of MBV_O and MBV_F ---")
    # Simulate both valves in parallel (independent cmd_prev each)
    o_prev = False
    f_prev = False
    events_o = [False, True, True, False]   # O: open at cycle 1, close at cycle 3
    events_f = [False, False, True, True]   # F: open at cycle 2, stays open

    o_changes = []
    f_changes = []
    for co, cf in zip(events_o, events_f):
        o_change, o_prev, _ = valve_tracking_cycle(co, o_prev, False)
        f_change, f_prev, _ = valve_tracking_cycle(cf, f_prev, False)
        o_changes.append(o_change)
        f_changes.append(f_change)

    check("MBV_O changes at cycles 1 and 3 only",
          o_changes == [False, True, False, True],
          f"Got: {o_changes}")
    check("MBV_F changes at cycle 2 only",
          f_changes == [False, False, True, False],
          f"Got: {f_changes}")
    check("MBV_O cycle 2 (F opens): MBV_O no spurious pulse",
          o_changes[2] == False)
    check("MBV_F cycle 1 (O opens): MBV_F no spurious pulse",
          f_changes[1] == False)

    # ─────────────────────────────────────────────────────────
    # 6. Abort-forced close does NOT generate cmd_change
    # ─────────────────────────────────────────────────────────
    print("\n--- 6. Abort-forced close: no cmd_change pulse ---")
    # Valve was open; abort fires this cycle forcing it closed
    # Pre-warm to establish cmd_prev=True
    results = simulate_sequence([
        (True,  False),   # warm-up: establish valve open
        (True,  False),   # 0: valve open, no abort
        (True,  True),    # 1: valve still commanded open, but abort fires
        (False, True),    # 2: abort still active, valve stays closed
        (False, False),   # 3: abort cleared, valve still closed
    ])
    results = results[1:]  # drop warm-up
    check("Cycle 0 (open, no abort): no change",       results[0][0] == False)
    check("Cycle 1 (abort fires, forces close): cmd_change = False",
          results[1][0] == False,
          "Abort closure communicated via Abort_Active flag, not cmd_change")
    check("Cycle 2 (abort holds): no change",          results[2][0] == False)
    check("Cycle 3 (post-abort, closed): no change",   results[3][0] == False)

    # Verify that after abort, mbv_open is actually False
    check("Cycle 1 post-abort: valve is False",        results[1][2] == False)

    # ─────────────────────────────────────────────────────────
    # 7. cmd_prev captures post-abort state (no spurious next-cycle pulse)
    # ─────────────────────────────────────────────────────────
    print("\n--- 7. cmd_prev captures post-abort state ---")
    # After abort clears, operator re-opens valve — THAT should generate a pulse
    results = simulate_sequence([
        (True,  False),   # 0: open
        (True,  True),    # 1: abort fires (forces closed, no cmd_change)
        (False, False),   # 2: abort cleared, valve still closed (operator hasn't re-opened)
        (True,  False),   # 3: operator re-opens valve
    ])
    check("Cycle 2 (after abort clear, still closed): no pulse",
          results[2][0] == False)
    check("Cycle 3 (operator re-opens): cmd_change = True",
          results[3][0] == True,
          "Operator re-opening after abort is a real commanded transition")

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
