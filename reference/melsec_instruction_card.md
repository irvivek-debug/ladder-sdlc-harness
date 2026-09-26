# MELSEC iQ-F (FX5) instruction-list card — harness subset

Our own summary for retrieval context. Page numbers refer to the MELSEC iQ-F FX5 Programming Manual
(Instructions) JY997D55801 unless noted. Read the manuals for authority; they are not reproduced here.

## Scan model
- Each scan: inputs are read, rungs execute top to bottom, then outputs are written. The last write to a
  device in a scan wins, so a bit driven by `OUT` in two rungs follows the later rung (a "double coil").
- Put step-transition rungs before the output rungs, so an output never lags its step by one scan.

## Devices (JY997D55401 §4.1)
- X (inputs) and Y (outputs) are **octal**: X0–X7, X10–X17, … (X8 does not exist).
- M, L (internal relays), T (timers), C (counters) and D (16-bit signed data registers) are decimal.
- SM400 is always ON. SM401 is always OFF. SM402 is ON only in the first scan after RUN.
- Constants: `K` is decimal (K50, K-500) and `H` is hexadecimal.

## Contacts (pp.114–121)
- `LD` / `LDI` start a condition with a normally open / normally closed contact.
- `AND` / `ANI` add a contact in series; `OR` / `ORI` add one in parallel.
- `LDP`, `ANDP`, `ORP` are rising-edge contacts: ON for one scan when the device turns ON.
- `LDF`, `ANDF`, `ORF` are the falling-edge equivalents.
- A T or C device used as a contact means "timer / counter done".
- Compares take two word operands: `LD= LD<> LD> LD< LD>= LD<=`, and the same with `AND`/`OR`.
  Example: `AND>= D100 D122` is true when D100 ≥ D122 (16-bit signed).

## Blocks (pp.123–128)
- A second `LD` inside a rung opens a block. `ANB` puts the last two blocks in series; `ORB` puts them in
  parallel.
- `MPS` pushes the current result, `MRD` reads it back, and `MPP` pops it. Each branch after them must end in
  an output, and MPS and MPP must balance within the rung.
- `INV` inverts the current result.

## Outputs
- `OUT Y/M/L` sets the device to the rung result, every scan. `SET` latches it ON; `RST` resets it (RST also
  clears T, C and D).
- `PLS` / `PLF` turn a device ON for one scan on the rising / falling edge of the rung result.
- `MOV S D` copies a word. `MOVP` executes only on the rising edge of the rung result. `+ S D` (D = D + S),
  `- S1 S2 D` (D = S1 − S2), and the `+P` / `-P` pulse forms work the same way; 16-bit results wrap.

## Timers (p.132; JY997D55401 pp.58–59)
- `OUT Tn K…` is a **100 ms** timer, `OUTH Tn` is **10 ms**, and `OUTHS Tn` is **1 ms**. On FX5 the
  instruction sets the base; the device number does not.
- A timer's value and contact update only when its coil executes. A contact read in a rung *before* the coil
  lags by one scan.
- Drive each timer from exactly one coil. A timer is non-retentive: it resets when its coil turns OFF.
- **FX3 migration trap.** On FX3U the *device number* set the base: T0–T199 100 ms, T200–T245 10 ms,
  T246–T249 1 ms retentive, T250–T255 100 ms retentive, T256–T511 1 ms (FX3 manual JY997D16601 p.88).
  A converted `OUT T200 K50` meant 0.5 s on FX3U, but is 5.0 s on FX5.

## Counters (p.135)
- `OUT Cn K…` counts rising edges of the rung result up to the preset; the contact is ON at the preset.
  `RST Cn` clears it.

## Master control (p.179)
- `MC Nn Mx` … `MCR Nn`: when the MC condition is OFF, OUT coils in the region turn OFF, non-retentive timers
  reset, and SET/RST devices and counters hold.

## End
- `END` ends the program. Nothing may follow it.
