; ST20 - pressure-decay leak test, EV battery pack enclosure (FX5U program block ST20_LEAKTEST)
; Migrated from FX3U in 2019. Parameters come from the I/O-list workbook parameter sheet.

# Parameters (authority: parameter sheet)
LD     SM400
MOV    K1450 D122       ; fill complete threshold 14.50 kPa
MOV    K30 D120         ; dP limit 0.30 kPa over the test window
MOV    K2000 D123       ; over-pressure trip 20.00 kPa

# PT-2001 under range (wire break)
LD<    D100 K-500
OUT    M292             ; PT-2001 signal fault

# Over-pressure trip, latched
LD>    D100 D123
SET    M291             ; over-pressure

# Supply air low while busy, latched
LD     M200
ANI    X22              ; PS-2009 supply air OK
SET    M293             ; supply air low

# Fault reset
LD     X1               ; PB-0002 fault reset
RST    M290
RST    M291
RST    M293

# Any fault
LD     M290
OR     M291
OR     M292
OR     M293
ORI    X0               ; ES-0001 E-stop circuit healthy (SAFETY input, read only)
OUT    M299             ; ST20 any fault
OUT    Y25              ; HL-2011 fault beacon

# S1 start: pallet arrives, auto, no fault, idle
LDP    X23              ; ZS-2008 pallet in test position
AND    X2               ; SS-0003 auto mode
ANI    M299
ANI    M200
SET    M200             ; busy
SET    M201             ; step CLAMP
RST    M210
RST    M211

# S2 CLAMP to FILL when clamp confirmed closed
LD     M201
AND    X20              ; ZS-2002A clamp closed
ANI    X21              ; ZS-2002B clamp open
RST    M201
SET    M202             ; step FILL

# Fill timeout
LD     M202
OUT    T21 K80          ; fill timeout 8.0 s

LD     T21
SET    M290             ; fill timeout alarm

# S3 FILL to STAB at fill threshold
LD     M202
AND>=  D100 D122
RST    M202
SET    M203             ; step STAB

# S4 STAB: settle with fill valve closed
LD     M203
OUT    T22 K50          ; stabilise 5.0 s

# Baseline pressure at end of stabilisation
LD     T22
MOVP   D100 D110        ; baseline pressure

# S5 STAB to TEST
LD     M203
AND    T22
RST    M203
SET    M204             ; step TEST

# S6 TEST: measure decay
LD     M204
OUT    T23 K100         ; test window 10.0 s

# Final pressure and decay at end of test
LD     T23
MOVP   D100 D111        ; final pressure
-      D110 D111 D112   ; dP = baseline - final

# Result
LD     M204
AND    T23
MPS
AND<=  D112 D120
SET    M210             ; PASS
MPP
AND>   D112 D120
SET    M211             ; FAIL

# S7 TEST to VENT
LD     M204
AND    T23
RST    M204
SET    M205             ; step VENT

# Fault during cycle: abort to VENT and FAIL
LD     M299
AND    M200
ANI    M205
ANI    M206
ANI    M207
RST    M201
RST    M202
RST    M203
RST    M204
SET    M205             ; step VENT
SET    M211             ; FAIL

# S8 VENT timer
LD     M205
OUT    T24 K5           ; vent 0.5 s

# S9 VENT to UNCLAMP only when vented below 1.00 kPa with a healthy PT (CE-ST20-08)
LD     M205
AND    T24
AND<   D100 K100        ; vented below 1.00 kPa
ANI    M292             ; PT-2001 signal healthy
RST    M205
SET    M206             ; step UNCLAMP

# S10 UNCLAMP to DONE when clamp confirmed open
LD     M206
AND    X21
ANI    X20
RST    M206
SET    M207             ; step DONE

# S11 DONE to idle when pallet leaves
LD     M207
ANI    X23
RST    M207
RST    M200             ; not busy

# OUTPUTS (after all transitions, so no output lags its step)
# Clamp solenoid held from CLAMP to VENT
LD     M201
OR     M202
OR     M203
OR     M204
OR     M205
OUT    Y20              ; XY-2002 clamp close

# Fill valve: FILL step, clamp confirmed closed, no fault
LD     M202
AND    X20              ; clamp closed interlock (CE-ST20-01)
ANI    M299
OUT    Y21              ; XV-2003 fill valve

# Vent valve: VENT step, latched over-pressure, or manual vent in manual mode
LD     M205
OR     M291             ; over-pressure keeps venting (CE-ST20-02)
LD     X25              ; PB-2010 manual vent
ANI    X2
ORB
OUT    Y22              ; XV-2004 vent valve

# Result signals to line controller
LD     M207
MPS
AND    M210
OUT    Y23              ; ST20 PASS to line controller
MPP
AND    M211
OUT    Y24              ; ST20 FAIL / reject request

END
