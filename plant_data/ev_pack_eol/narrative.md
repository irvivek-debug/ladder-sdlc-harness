# Control Narrative — EV Battery Pack End-of-Line Cell (ST10 / ST20 / ST30)

Document CN-EOL-01 · Revision E · Synthetic example for the Ladder SDLC Harness

> All values are **representative**, chosen to be plausible for a battery-enclosure pressure-decay test.
> They are not any manufacturer's specification. The authoritative parameter values are held on the
> *Parameters* sheet of `io_list.xlsx`.

## 1. Purpose

This narrative describes the intended behaviour of the three stations of the end-of-line cell. Maintenance
and controls engineers use it to understand the PLC program. The cause-and-effect matrix
(`cause_effect.xlsx`) is the formal statement of interlocks and trips.

## 2. Cell overview

One MELSEC iQ-F FX5U controller runs three program blocks, one per station:

| Station | Program block | Function |
|---|---|---|
| ST10 | ST10_CONVEYOR | Pallet conveyor feeding the test position |
| ST20 | ST20_LEAKTEST | Pressure-decay leak test of the pack enclosure |
| ST30 | ST30_HIPOT | High-voltage insulation (HiPot) test — **SAFETY-classified** |

Common inputs: E-stop chain healthy (ES-0001, X0), fault reset (PB-0002, X1) and auto mode (SS-0003, X2).

## 3. ST10 — Pallet conveyor

The conveyor motor M-1001 runs in auto mode while no ST10 fault is present. Pallets travel against a spring
stopper at the test position, and the at-stop photo-eye PE-1001 reports "pallet in position" to ST20.

When the line controller requests a release (RQ-1005, rising edge), the stopper solenoid XY-1004 drops the
stopper for 2.0 s so the pallet can leave.

**Jam detection:** if the entry photo-eye PE-1002 stays blocked for more than 5.0 s while the conveyor runs,
the conveyor stops and a jam alarm is raised until it is reset.

**Stops:** a motor overload (MOL-1001) or the E-stop chain stops the conveyor immediately.

## 4. ST20 — Pressure-decay leak test

The pack enclosure is clamped, filled with regulated air to the test pressure and isolated. The pressure
decay over a fixed window is compared with a limit. PT-2001 is read through the FX5-4AD-ADP analog adapter,
which is scaled so that 0..10000 represents 0..100.00 kPa(g).

### 4.1 Start

A cycle starts when a pallet arrives in the test position (ZS-2008, rising edge), provided that:

- the cell is in auto mode;
- no ST20 fault is active;
- the station is idle.

A pallet sensor that drops and returns while a test is running must not restart the sequence.

### 4.2 Clamp

The clamp solenoid XY-2002 closes the clamp. The sequence continues only when ZS-2002A (closed) is made and
ZS-2002B (open) is clear. The clamp stays closed from CLAMP until VENT is complete.

### 4.3 Fill

The fill valve XV-2003 opens and the pack fills towards the regulator setpoint (15.2 kPa). The fill valve may
only be open while the clamp is confirmed closed; if the clamp is lost, the fill valve closes immediately.

The fill is complete when PT-2001 reaches 14.50 kPa. If that pressure is not reached within 8.0 s, a
fill-timeout alarm is raised and the cycle aborts to VENT with a FAIL result.

### 4.4 Stabilise

With the fill valve closed, the pack is left to settle for 3 s so that the adiabatic temperature transient
decays. At the end of stabilisation the baseline pressure is recorded.

### 4.5 Test

The pack stays isolated for the 10.0 s test window. At the end of the window the final pressure is recorded
and the decay is calculated as baseline minus final.

### 4.6 Decision

- A decay at or below 0.30 kPa over the window is a **PASS**.
- A decay above 0.30 kPa is a **FAIL**: the pack is rejected for rework.

### 4.7 Vent, unclamp and result

The vent valve XV-2004 opens for 0.5 s. The clamp is released only when the pack is vented below 1.00 kPa and
the pressure signal is healthy. If either condition is not met, the station holds in VENT with the vent open.

When the clamp is confirmed open, the station reports DONE. The PASS (RS-2006) or FAIL (RS-2007) signal is
given to the line controller only at DONE, and the station returns to idle when the pallet leaves.

In manual mode, the manual vent pushbutton PB-2010 opens the vent valve so a technician can depressurise a
pack by hand.

### 4.8 Alarms and faults

| Alarm | Condition | Action |
|---|---|---|
| Fill timeout | Test pressure not reached within 8.0 s | Abort to VENT, FAIL |
| Over-pressure | PT-2001 above 20.00 kPa (latched) | Fill closed, vent held open, FAIL |
| PT-2001 signal fault | Reading below −5.00 kPa (wire break) | Cycle start inhibited; unclamp held |
| Supply air low | PS-2009 lost while busy (latched) | Abort to VENT, FAIL |

All faults light the ST20 fault beacon HL-2011. Latched alarms clear with the fault reset once their cause
has gone. If the E-stop chain is lost during a cycle, the cycle aborts to VENT with a FAIL result.

The cycle-time allowance for ST20, from pallet arrival to DONE, is 23.0 s.

## 5. Safety

- The E-stop is hard-wired through a safety relay. The standard program only **reads** its healthy contact
  (ES-0001), and must never be the only means of stopping hazardous motion.
- ST30 applies high voltage. Its HV-enable and beacon outputs, and the guard-door input, are
  **SAFETY-classified**. Changes to rungs that drive them follow the functional-safety change process and are
  never made by an AI assistant.
- AI assistance is limited to understanding, documenting, testing and proposing changes to non-safety logic.
  Every proposal is proven on the simulator and signed off by a controls engineer.

## 6. ST30 — HV insulation (HiPot) test

When a pallet is in ST30 (ZS-3001), the guard door is closed (ZS-3002) and the E-stop chain is healthy, the
tester is enabled (HP-3005) and the HV beacon HL-3006 lights. The tester reports PASS (HP-3003) or FAIL
(HP-3004) after its internal 3.0 s test, and HV is removed as soon as a result is latched.

Opening the guard door or losing the E-stop chain removes HV at once. Results reset when the pallet leaves.

## 7. Revision history

| Rev | Date | Change |
|---|---|---|
| A | 2016-03 | Initial issue (FX3U) |
| B | 2017-11 | Over-pressure trip added |
| C | 2019-06 | Controller migrated FX3U → FX5U; program converted |
| D | 2021-02 | Manual vent pushbutton PB-2010 added (MOC-2021-031) |
| E | 2022-08 | ST30 HiPot station added |
