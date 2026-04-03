# Ignition Firing Logic — Complete Walkthrough

## Overview

This document explains the complete firing sequence from operator arm to e-match pulse, including all safety interlocks, per-cycle monitoring, and event latching.

---

## Part 1: Per-Cycle vs Per-Sequence Execution

### Per-Cycle (Current Implementation)

Per-cycle code runs **every single control cycle** (0.1 seconds in our system).

```rvl
const CYCLE: float = 0.1

loop monitor_safety:
    if |System_Max_P| > MAX_SAFE_P:
        |Abort_Active| = True
```

**Characteristics:**
- Executes every 0.1 seconds continuously
- Each execution checks current state: "Is condition true RIGHT NOW?"
- No memory between cycles — checks are fresh each cycle
- Instant reaction to state changes
- **Perfect for:** Safety monitoring, continuous checks, reactive controls

**Example:** If pressure spikes over MAX_SAFE_P, the abort trigger fires on the very next cycle (0.1s later).

### Per-Sequence (For Future Multi-Step Procedures)

Per-sequence code executes **once when commanded**, pauses at wait statements, then resumes when wait completes.

```rvl
sequence ignition_countdown:
    |Ignition_Output| = False
    wait 3.0  # pause here for 3 seconds, then continue
    |Ignition_Output| = True   # this runs after 3 seconds
    wait CYCLE
    |Ignition_Output| = False
```

**Characteristics:**
- Starts when operator sends `|sequence.command| = Cmd.run`
- Remembers execution position (line number) across cycles
- Pauses at `wait` and `wait until` statements
- Resumes from saved position when condition met
- **Perfect for:** Multi-step procedures, timed sequences, warm-up routines, countdowns

**Why we're not using sequences yet:** Firing logic needs per-cycle instant reaction for safety. Sequences would delay critical safety checks.

---

## Part 2: Complete Firing Logic Walkthrough

### Cycle 0: Operator Arms System

```
Operator Action: Click "ARM IGNITION" button
↓
Code Effect: |Ignition_Armed| = True
```

The operator explicitly arms the ignition system. This is a **gate** — fire commands will be ignored if this is False.

---

### Cycle 1+: Every Cycle — Compute Readiness

**In `ignition_sequence` loop:**

```rvl
if |Ignition_Armed| and not |Abort_Active| and |System_Max_P| > 0.0 and |System_Max_P| < MAX_SAFE_P:
    |Ignition_Ready| = True
else:
    |Ignition_Ready| = False
```

**Readiness Check (4 conditions, ALL must be true):**

| Condition | What It Checks | Why |
|---|---|---|
| `\|Ignition_Armed\|` | Did operator explicitly arm? | Prevents accidental fire |
| `not \|Abort_Active\|` | Is system NOT in abort state? | Abort overrides everything |
| `\|System_Max_P\| > 0.0` | Is there at least some pressure? | Can't ignite with zero pressure |
| `\|System_Max_P\| < MAX_SAFE_P` | Is pressure below overpressure limit (1240 PSI)? | Overpressure = automatic abort, no fire |

**Result:**
- All true → `|Ignition_Ready| = True` (green light for fire)
- Any false → `|Ignition_Ready| = False` (not ready, fire blocked)

---

### Cycle 1+: Every Cycle — E-Match Continuity Check

**In `ematch_continuity` loop:**

The operator can optionally test the e-match bridgewire continuity before firing.

```rvl
if |Ematch_Test_Cmd|:
    |Ematch_Test_Cmd| = False      # consume the command
    |Ematch_Test_Result| = |Ematch_Continuity_Input|  # snapshot reading
    |Ematch_Test_Run| = True       # mark that we ran a test

if |Ematch_Test_Run| and |Ematch_Test_Result| and not |Abort_Active|:
    |Ematch_Ready| = True
else:
    |Ematch_Ready| = False
```

**E-Match Readiness Check (3 conditions):**

| Condition | What It Checks | Why |
|---|---|---|
| `\|Ematch_Test_Run\|` | Has operator run continuity test? | Must test before trusting continuity |
| `\|Ematch_Test_Result\|` | Did test pass (continuity OK)? | Broken bridgewire = no ignition |
| `not \|Abort_Active\|` | Is system NOT in abort? | Abort blocks everything |

**Command Consumption:** When operator clicks "TEST CONTINUITY", `|Ematch_Test_Cmd|` is set to True. On the very next cycle, the loop reads it, clears it, and takes the snapshot. This ensures one test per click.

---

### Cycle N: Operator Sees Ready State

**UI Display (operator sees):**
```
[ARMED] indicator on
[GREEN] Ignition_Ready = True    ✓ All conditions met
[GREEN] Ematch_Ready = True      ✓ Bridgewire continuity confirmed
[PRESSURE] 1050 PSI              ✓ In safe range
[ALTITUDE] 45000 ft
```

Operator is now authorized to fire.

---

### Cycle N+1: Operator Chooses Dry Run (Optional)

**Optional Pre-Fire Test:**

```
Operator Action: Check "Enable Dry Run" checkbox
↓
Code Effect: |Dry_Run_Active| = True

Operator Action: Click "TEST FIRE" button
↓
Code Effect: |Dry_Run_Fire_Cmd| = True
```

**In `ignition_sequence` loop:**

```rvl
if |Dry_Run_Fire_Cmd|:
    |Dry_Run_Fire_Cmd| = False         # consume command
    if |Dry_Run_Active| and |Ignition_Ready|:
        |Dry_Run_Passed| = True        # latch success
```

**What Happens:**
- Sequence logic executes end-to-end
- All readiness interlocks are checked (identical to live fire)
- `|Ignition_Output|` is NOT set (no hardware pulse)
- `|Dry_Run_Passed|` latches to True (event record)

**Result in UI:**
```
[DRY RUN PASSED] ✓ All logic works, safe to fire for real
```

---

### Cycle N+2: Operator Unselects Dry Run (if it was enabled)

```
Operator Action: Uncheck "Enable Dry Run"
↓
Code Effect: |Dry_Run_Active| = False
```

System is now in live-fire mode.

---

### Cycle N+3: Operator Fires

```
Operator Action: Click "FIRE" button
↓
Code Effect: |Ignition_Fire_Cmd| = True
```

**In `ignition_sequence` loop (SAME CYCLE):**

```rvl
if |Ignition_Fire_Cmd|:
    |Ignition_Fire_Cmd| = False        # consume command (one-time only)
    if |Ignition_Ready|:               # final check
        |Ignition_Output| = True       # SET HARDWARE OUTPUT
        |Ignition_Fired| = True        # record event for telemetry
```

**What Happens:**
1. Fire command consumed (cleared immediately)
2. Readiness checked one final time
3. `|Ignition_Output|` set to True
4. `|Ignition_Fired|` latches to True (permanent record)

---

### Cycle N+4: Hardware Output

**In `write_hardware` loop:**

```rvl
loop write_hardware:
    |sv0.value| = |MBV_O.open|
    |sv1.value| = |MBV_F.open|
    |sv2.value| = |Ignition_Output|   # <- writes True to relay sv2
```

**Hardware Effect:**
- Relay sv2 is energized
- E-match circuit is closed
- Bridgewire current flows
- Bridgewire heats and ignites e-match

**Pulse Duration:** 1 cycle = 0.1 seconds

---

### Cycle N+5: Pulse Ends

**In `ignition_sequence` loop:**

```rvl
# At the top of every cycle, clear the output
|Ignition_Output| = False
```

**Hardware Effect:**
- Relay sv2 is de-energized
- E-match circuit is opened
- Bridgewire current stops
- (If e-match was hot enough to ignite, ignition has occurred)

---

### Post-Fire State

**Permanent Records:**
- `|Ignition_Fired| = True` — stays latched (event happened)
- `|Dry_Run_Passed| = True` (if dry run was run) — latched event
- All sensor values at time of fire logged to telemetry

**System State:**
- `|Ignition_Armed|` can remain True (operator can arm and fire again if needed)
- `|Ignition_Ready|` recalculates every cycle (updates if pressure changes)
- `|Ignition_Output|` is False (pulse is over)
- Any post-fire abort/recovery procedures handled by safety loop

---

## Part 3: Safety Interlocks (Always Active)

These checks run **every single cycle**, independent of firing logic:

### Overpressure Abort

```rvl
if |System_Max_P| > MAX_SAFE_P:
    |Abort_Cause_Overpressure| = True
    |Abort_Active| = True
```

**Effect:**
- Immediately closes both main bleed valves (`MBV_O.open = False`, `MBV_F.open = False`)
- Blocks ignition (`|Ignition_Armed|` forced to False)
- Blocks continuity readiness
- Fired alert: `alert.overpressure_pt_ot.fired` (and similar for ft, pt5)

### E-Stop Abort

```rvl
if |EStop_Cmd|:
    |Abort_Cause_EStop| = True
    |Abort_Active| = True
    |EStop_Cmd| = False  # consume command
```

**Effect:** Same as overpressure — immediate system safe.

### Pressure Warning Alerts (Non-Latching)

```rvl
alert warn_pt_ot:
    severity = Severity.warning
    trigger = |PT_OT.value| > WARN_P
```

**Effect:** Alert fires when condition is true, clears when condition becomes false. Operator sees warnings in alert console but system does NOT abort.

---

## Part 4: Command Consumption Pattern

All operator commands are **consumed on first read**:

```
Cycle N:     |Fire_Cmd| set by operator = True
Cycle N+1:   Code reads: if |Fire_Cmd|:
                            |Fire_Cmd| = False    # consumed
                            ... take action ...
Cycle N+2:   Fire_Cmd is now False, action only happened once
```

This ensures:
- Double-clicking "FIRE" doesn't cause multiple ignitions
- Multiple cycles don't re-trigger the same command
- Each click = exactly one action

---

## Part 5: Event Latching

Some channels **latch** — once set to True, they stay True until explicitly reset:

| Channel | Set By | Reset By | Purpose |
|---|---|---|---|
| `\|Ignition_Fired\|` | Fire action | (stays True for session) | Event record: "fire happened this session" |
| `\|Dry_Run_Passed\|` | Dry run success | (stays True for session) | Event record: "dry run succeeded" |
| `\|Ematch_Test_Run\|` | Continuity test | (stays True for session) | Event record: "test was run" |
| `\|Abort_Active\|` | Overpressure / E-Stop | `\|Reset_Abort\|` command | Must be explicitly cleared when safe |

**Why Latch?**
- Telemetry captures full history (what events happened this session)
- Can't accidentally lose record of abort by pressure dropping
- Operator must consciously reset abort (safety confirmation)

---

## Part 6: Typical Mission Timeline

```
T=0s      Operator arms system
          |Ignition_Armed| = True
          UI shows: [ARMED]

T=0.5s    Operator runs continuity test
          |Ematch_Test_Cmd| = True
          Next cycle: test reads and latches result
          UI shows: [GREEN] Ematch_Ready

T=1.0s    Operator enables dry run
          |Dry_Run_Active| = True
          Operator clicks "TEST FIRE"
          |Dry_Run_Fire_Cmd| = True
          Next cycle: logic runs, no hardware pulse
          UI shows: [DRY RUN PASSED]

T=1.5s    Operator disables dry run
          |Dry_Run_Active| = False
          System now in live-fire mode

T=2.0s    Operator is ready, system is ready
          UI shows: [ARMED], [Ignition_Ready], [Ematch_Ready], [GREEN]
          Operator clicks "FIRE"
          |Ignition_Fire_Cmd| = True

T=2.1s    Fire command processed in ignition_sequence loop
          |Ignition_Output| = True (one cycle only)
          write_hardware loop energizes relay sv2
          E-match fires!

T=2.2s    Pulse ends, |Ignition_Output| = False
          Relay de-energized
          System ready for next operation

T=2.3s onward
          Post-fire telemetry logged
          |Ignition_Fired| = True (permanent record)
          System can recover or be reset for next operation
```

---

## Part 7: Why Per-Cycle Works for This System

| Reason | Implication |
|---|---|
| Safety requires instant reaction | Abort must act within 0.1s of pressure spike |
| Fire is a single discrete action | Command consumed, output pulsed, done — fits per-cycle model |
| Readiness is always being evaluated | Per-cycle check gives operator real-time "ready/not ready" status |
| No waiting between logic steps | Arm → compute ready → command fire → pulse → done in ~0.3s |
| Hardware relay is discrete (on/off) | One-cycle pulse is appropriate timing (0.1s is long enough for bridgewire) |

---

## Part 8: Future Enhancement — Multi-Step Procedures with Sequences

If we add a **pressurization procedure**, sequences become valuable:

```rvl
sequence pressurize_and_fire:
    # Step 1: Start pressurization
    |MBV_O.open| = True
    wait 2.0  # hold oxidizer open for 2 seconds

    # Step 2: Wait for pressure to build (or timeout)
    wait until |PT_OT.value| > 1000.0:
        timeout 10.0:
            |Abort_Active| = True  # timeout -> abort
            pass  # exit sequence

    # Step 3: Final readiness check before fire
    if |Ignition_Ready|:
        |Ignition_Output| = True
        wait CYCLE
        |Ignition_Output| = False

    # Step 4: Begin recovery
    |MBV_O.open| = False
    |MBV_F.open| = False
```

**How this would work:**
- Operator clicks "PRESSURIZE AND FIRE"
- Sequence runs: opens valve, waits, checks pressure, fires, closes valve
- Each step waits for its condition before proceeding
- Multi-second procedure atomically (can't be interrupted mid-step)

This combines the **speed of per-cycle readiness checks** with the **controlled timing of sequences**.

---

## Summary

| Phase | Timing | Key Code Location | User Impact |
|---|---|---|---|
| **Arm** | One-time | UI button | Gates all fire commands |
| **Compute Readiness** | Every cycle | `ignition_sequence` loop | Real-time "ready/not ready" display |
| **Test (Optional)** | One-time | `ematch_continuity` loop | Operator confirms bridgewire before fire |
| **Dry Run (Optional)** | One-time | `ignition_sequence` loop | Tests full logic without hardware pulse |
| **Fire** | One-time | `ignition_sequence` loop | Operator fires |
| **Pulse** | 1 cycle (0.1s) | `write_hardware` loop | Hardware energizes relay, e-match ignites |
| **Record** | Permanent | Event latches | Telemetry captures "fire happened" |

---

## Questions & Contact

For questions about this logic, refer to the code at:
- **Per-cycle checks:** `cold_flow_code/cold_flow_test.rvl`, lines `ignition_sequence` loop
- **Safety interlocks:** `monitor_safety` loop
- **E-match continuity:** `ematch_continuity` loop
- **Hardware mapping:** `write_hardware` loop
