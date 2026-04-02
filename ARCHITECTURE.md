# SSI Revel Control System — Architecture Reference

## Repo Structure

```
SSIRevelLinux/
├── cold-flow-code/               ← ACTIVE WORK (real hardware config)
│   ├── cold_flow_test.rvl        ← Main control logic (all safety/abort/ignition code)
│   ├── system.yaml               ← Revel project config
│   └── devices/                  ← NI hardware device configurations
│       ├── NI_CDAQ_CHASSIS_5944be.yaml           (Ethernet cDAQ-9189, IP 172.16.23.1)
│       ├── NI_9205_b9f2cd.yaml                   (32ch analog input, slot 5, pt0–pt31)
│       ├── NI_9213_25f73a.yaml                   (16ch Type-K thermocouple, slot 8, tc0–tc15, degF)
│       ├── NI_9219_d9y4gbnz2hs.yaml              (4ch universal input, slot 4, strain gauge, LC0–LC3)
│       ├── NI_9401_ec6a3f.yaml                   (DIO, slot 2, 5V TTL, servo0/servo1 pulse gen)
│       ├── NI_UNSUPPORTED_MODULE_adaf52.yaml      (NI 9482, slot 3, sv0–sv3 relay)
│       └── NI_UNSUPPORTED_MODULE_adaf52_copy.yaml (NI 9482, slot 1, sv10–sv13 relay)
├── 4card/                        ← Reference hardware config (canonical device YAMLs)
│   ├── system.yaml
│   └── devices/
├── Demo/                         ← Reference only (servo PWM demo)
│   └── demo.rvl                  (two servos, 5ms period, 0.5ms–2.5ms pulse)
├── tests/                        ← All test scripts (Python, no runtime needed)
│   ├── test_overpressure_warnings.py          (Task 1 reference logic, 32 tests)
│   └── test_rvl_overpressure_validation.py    (Task 1 .rvl structural + sim, 30 tests)
├── MANUAL.md                     ← Revel framework reference
└── ARCHITECTURE.md               ← This file
```

## Hardware Channel Mapping

The .rvl logic uses descriptive names mapped to hardware channels via `read_hardware` and `write_hardware` loops.
**Verify these mappings against your wiring harness before ops.**

### Inputs (read_hardware loop)
| Logic Name   | HW Channel | Card     | Slot | Description                         |
|-------------|------------|----------|------|-------------------------------------|
| PT_OT.value | pt0.value  | NI 9205  | 5    | Oxidizer tank pressure (PSI)        |
| PT_FT.value | pt1.value  | NI 9205  | 5    | Fuel tank pressure (PSI)            |
| PT5.value   | pt2.value  | NI 9205  | 5    | [VERIFY physical location]          |
| TC1.value   | tc0.value  | NI 9213  | 8    | Thermocouple (degF, Type K)         |
| LC0.value   | NI_9219_ch0| NI 9219  | 4    | Load cell ch0 [VERIFY assignment]   |
| LC1.value   | NI_9219_ch1| NI 9219  | 4    | Load cell ch1 [VERIFY assignment]   |
| LC2.value   | NI_9219_ch2| NI 9219  | 4    | Load cell ch2 [VERIFY assignment]   |
| LC3.value   | NI_9219_ch3| NI 9219  | 4    | Load cell ch3 [VERIFY assignment]   |

### Outputs (write_hardware loop)
| Logic Name       | HW Channel | Card     | Slot | Description                    |
|-----------------|------------|----------|------|--------------------------------|
| MBV_O.open      | sv0.value  | NI 9482  | 3    | Main bleed valve, oxidizer     |
| MBV_F.open      | sv1.value  | NI 9482  | 3    | Main bleed valve, fuel         |
| Ignition_Output | sv2.value  | NI 9482  | 3    | E-match trigger (1-cycle pulse)|

### Not Yet Assigned
| Logic Name               | Needs             | Notes                                    |
|--------------------------|-------------------|------------------------------------------|
| Ematch_Continuity_Input  | Digital input     | Assign DIO ch on NI 9401 (slot 5)        |

## cold_flow_test.rvl — Channel Inventory

### Constants
| Name        | Value    | Purpose                        |
|-------------|----------|--------------------------------|
| CYCLE       | 0.1 s    | Loop execution period          |
| MAX_SAFE_P  | 1240 PSI | Overpressure / abort threshold |
| WARN_P      | 1150 PSI | Early warning threshold        |

### Sensor Channels (float)
| Channel       | Units | Description                  | Hardware         |
|---------------|-------|------------------------------|------------------|
| PT_OT.value   | PSI   | Oxidizer tank pressure       | pt0 (NI 9205)   |
| PT_FT.value   | PSI   | Fuel tank pressure           | pt1 (NI 9205)   |
| PT5.value     | PSI   | Secondary pressure point     | pt2 (NI 9205)   |
| TC1.value     | degF  | Temperature measurement      | tc0 (NI 9213)   |
| System_Max_P  | PSI   | max(PT_OT, PT_FT, PT5)       | computed         |

### Internal State (float)
| Channel    | Description                     |
|------------|---------------------------------|
| PT_OT_Prev | Previous cycle PT_OT (for delta)|
| PT_FT_Prev | Previous cycle PT_FT (for delta)|

### Valve / Actuator Channels (bool)
| Channel         | Description                                             |
|-----------------|---------------------------------------------------------|
| MBV_O.open      | COMMANDED open/closed — oxidizer (no position feedback) |
| MBV_F.open      | COMMANDED open/closed — fuel (no position feedback)     |
| MBV_O.cmd_prev  | Previous cycle commanded state (internal)               |
| MBV_F.cmd_prev  | Previous cycle commanded state (internal)               |
| MBV_O.cmd_change| 1-cycle pulse on operator-commanded transition          |
| MBV_F.cmd_change| 1-cycle pulse on operator-commanded transition          |

### Warning Flags (bool) — set by monitor_safety loop
| Channel           | Condition                       | Latching? |
|-------------------|---------------------------------|-----------|
| Warn_PT_OT        | PT_OT > WARN_P                  | No        |
| Warn_PT_FT        | PT_FT > WARN_P                  | No        |
| Warn_PT5          | PT5  > WARN_P                   | No        |
| Overpressure_PT_OT| PT_OT > MAX_SAFE_P              | No        |
| Overpressure_PT_FT| PT_FT > MAX_SAFE_P              | No        |
| Overpressure_PT5  | PT5  > MAX_SAFE_P               | No        |
| RV_O_Lifted       | ΔPT_OT > 20 PSI/cycle, MBV_O closed | Sticky† |
| RV_F_Lifted       | ΔPT_FT > 20 PSI/cycle, MBV_F closed | Sticky† |

### Flow / State Flags (bool)
| Channel     | Condition                           |
|-------------|-------------------------------------|
| Ox_Flowing  | PT_OT > 50 PSI AND MBV_O open       |
| Fuel_Flowing| PT_FT > 50 PSI AND MBV_F open       |

### Abort State (bool)
| Channel                 | Description                                               |
|-------------------------|-----------------------------------------------------------|
| EStop_Cmd               | Operator E-Stop command (consumed same cycle)             |
| Abort_Active            | Latching. Set by overpressure OR E-Stop                   |
| Abort_Cause_Overpressure| Latching. Set when overpressure triggered abort           |
| Abort_Cause_EStop       | Latching. Set when operator E-Stop triggered abort        |
| Reset_Abort             | Operator command. Clears abort+causes if pressure safe    |

## Loops in cold_flow_test.rvl

```
read_hardware    — runs every 0.1s
  Maps hardware channel names to descriptive logic names.
  pt0→PT_OT, pt1→PT_FT, pt2→PT5, tc0→TC1

monitor_safety   — runs every 0.1s
  1. Valve transition detection (cmd_change pulses)
  2. System_Max_P = max of all 3 PTs
  3. Per-sensor WARN/OVERPRESSURE flags
  4. Relief valve lift detection (oxidizer + fuel)
  5. Track PT_OT_Prev / PT_FT_Prev
  6. Ox_Flowing / Fuel_Flowing state
  7. Abort trigger 1: overpressure → Cause_Overpressure + Abort_Active
  8. Abort trigger 2: EStop_Cmd → Cause_EStop + Abort_Active + consume cmd
  9. Abort enforcement (close both MBVs)
  10. Abort reset: clears Active + both causes (requires pressure safe)

ematch_continuity — runs every 0.1s
  Snapshot-on-command bridgewire continuity test

ignition_sequence — runs every 0.1s
  ARM → READY → FIRE interlocks, dry run path, live fire path

write_hardware   — runs every 0.1s
  Maps logic channel states to physical hardware outputs.
  MBV_O.open→sv0, MBV_F.open→sv1, Ignition_Output→sv2
```

## Implementation Roadmap

| # | Task                              | Status     | Tests                                      |
|---|-----------------------------------|------------|--------------------------------------------|
| 1 | Per-sensor overpressure warnings  | ✅ Done    | tests/test_overpressure_warnings.py (32)   |
|   |                                   |            | tests/test_rvl_overpressure_validation.py (30) |
| 2 | Relief valve lift warnings (fuel) | ✅ Done    | tests/test_relief_valve_detection.py (20)  |
|   |                                   |            | tests/test_rvl_rv_validation.py (12)       |
| 3 | Clearly labeled pressures + temps | ✅ Done    | tests/test_sensor_labeling.py (19)         |
| 4 | Valve state tracking              | ✅ Done    | tests/test_valve_state_tracking.py (21)    |
|   |                                   |            | tests/test_rvl_valve_validation.py (17)    |
| 5 | Abort logic hardening + E-Stop    | ✅ Done    | tests/test_abort_estop.py (48)             |
|   |                                   |            | tests/test_rvl_abort_validation.py (17)    |
| 6 | Ignition logic                    | ✅ Done    | tests/test_ignition_logic.py (29)          |
|   |                                   |            | tests/test_rvl_ignition_validation.py (17) |
| 7 | E-match continuity test           | ✅ Done    | tests/test_ematch_continuity.py (28)       |
|   |                                   |            | tests/test_rvl_ematch_dryrun_validation.py |
| 8 | Ignition sequence dry run         | ✅ Done    | tests/test_ignition_dry_run.py (22)        |
|   |                                   |            | tests/test_rvl_ematch_dryrun_validation.py (24) |

† **Sticky** = flag stays True while the valve remains closed (resets to False when operator opens the valve). This preserves the observation "the relief lifted during this closed-valve period" without requiring a separate latch mechanism. Telemetry logs capture the full history.

## Design Rules (operator safety)
- **Never lie.** Display raw sensor values. No inferred or extrapolated states.
- **Warn on threshold only.** If pressure > X, flag it. No trend analysis claiming "you're blowing down."
- **Abort is deterministic.** Explicit threshold, no heuristics.
- **Warnings are non-latching.** They reflect current reality, not history (logs handle history).
- **Abort IS latching.** Requires deliberate operator reset with confirmed safe pressure.
