# SSI Revel Control System — Architecture Reference

## Repo Structure

```
SSIRevelLinux/
├── No-Hardware Sim/              ← ACTIVE WORK (do not touch 4card/Demo)
│   ├── cold_flow_test.rvl        ← Main control logic (all safety/abort/ignition code lives here)
│   └── system.yaml               ← Virtual channel declarations for simulation
├── 4card/                        ← Reference only (real NI hardware config)
│   ├── system.yaml
│   └── devices/
│       ├── NI_CDAQ_CHASSIS_5944be.yaml   (Ethernet cDAQ-9189, IP 172.16.23.1)
│       ├── NI_9205_b9f2cd.yaml           (32ch analog input, 0-10V diff, 7812.5 Hz)
│       ├── NI_9213_25f73a.yaml           (16ch Type-K thermocouple, Fahrenheit)
│       └── NI_9401_ec6a3f.yaml           (10ch DIO, 5V TTL, pulse gen for servos)
├── Demo/                         ← Reference only (servo PWM demo)
│   └── demo.rvl                  (two servos, 5ms period, 0.5ms–2.5ms pulse)
├── tests/                        ← All test scripts (Python, no runtime needed)
│   ├── test_overpressure_warnings.py          (Task 1 reference logic, 32 tests)
│   └── test_rvl_overpressure_validation.py    (Task 1 .rvl structural + sim, 30 tests)
├── MANUAL.md                     ← Revel framework reference
└── ARCHITECTURE.md               ← This file
```

## cold_flow_test.rvl — Channel Inventory

### Constants
| Name        | Value    | Purpose                        |
|-------------|----------|--------------------------------|
| CYCLE       | 0.1 s    | Loop execution period          |
| MAX_SAFE_P  | 1240 PSI | Overpressure / abort threshold |
| WARN_P      | 1150 PSI | Early warning threshold        |

### Sensor Channels (float)
| Channel       | Units | Description                  | Hardware (future) |
|---------------|-------|------------------------------|-------------------|
| PT_OT.value   | PSI   | Oxidizer tank pressure       | NI 9205 analog in |
| PT_FT.value   | PSI   | Fuel tank pressure           | NI 9205 analog in |
| PT5.value     | PSI   | Secondary pressure point     | NI 9205 analog in |
| TC1.value     | °C    | Temperature measurement      | NI 9213 TC        |
| System_Max_P  | PSI   | max(PT_OT, PT_FT, PT5)       | computed          |

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
| RV_O_Lifted       | ΔPT_OT > 20 PSI/cycle, MBV_O closed | Sticky |
| RV_F_Lifted       | ΔPT_FT > 20 PSI/cycle, MBV_F closed | Sticky |

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
monitor_safety   — runs every 0.1s
  1. System_Max_P = max of all 3 PTs
  2. Per-sensor WARN/OVERPRESSURE flags
  3. Relief valve lift detection (oxidizer ✓, fuel TODO)
  4. Track PT_OT_Prev / PT_FT_Prev
  5. Ox_Flowing / Fuel_Flowing state
  6. Abort trigger 1: overpressure → Cause_Overpressure + Abort_Active
  7. Abort trigger 2: EStop_Cmd → Cause_EStop + Abort_Active + consume cmd
  8. Abort enforcement (close both MBVs)
  9. Abort reset: clears Active + both causes (requires pressure safe)

simulate_pressure — runs every 0.1s (NO-HW SIM ONLY — remove for real hardware)
  - PT_OT: +10 PSI/cycle (closed), -25 PSI/cycle (open), wraps at 1300
  - PT_FT: +8 PSI/cycle, wraps at 1300
  - PT5:   +5 PSI/cycle, wraps at 1300
  - TC1:   +0.1°C/cycle, resets to 70 at 500°C
```

## Design Rules (operator safety)
- **Never lie.** Display raw sensor values. No inferred or extrapolated states.
- **Warn on threshold only.** If pressure > X, flag it. No trend analysis claiming "you're blowing down."
- **Abort is deterministic.** Explicit threshold, no heuristics.
- **Warnings are non-latching.** They reflect current reality, not history (logs handle history).
- **Abort IS latching.** Requires deliberate operator reset with confirmed safe pressure.
