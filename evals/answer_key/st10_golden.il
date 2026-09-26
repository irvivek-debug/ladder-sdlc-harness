; ST10 - pallet conveyor feeding the ST20 test position (FX5U program block ST10_CONVEYOR)

# Motor overload
LDI X13 ; MOL-1001 overload healthy
OUT M191 ; conveyor motor overload

# Jam detection: entry eye blocked 5 s while running
LD X11 ; PE-1002 entry eye
AND Y10
OUT T10 K50 ; jam timer 5.0 s
LD T10
SET M190 ; conveyor jam

# Fault reset
LD X1 ; PB-0002 fault reset
RST M190

# Any fault
LD M190
OR M191
ORI X0 ; ES-0001 E-stop circuit healthy (SAFETY input, read only)
OUT M199 ; ST10 any fault

# Conveyor motor
LD X2 ; SS-0003 auto mode
ANI M199
OUT Y10 ; M-1001 conveyor motor

# Pallet in position
LD X10 ; PE-1001 pallet at stop
OUT M100 ; pallet in position (ST20 handshake)

# Stopper release on request
LDP X14 ; RQ-1005 release request from line controller
SET Y11 ; XY-1004 stopper release
LD Y11
OUT T11 K20 ; release pulse 2.0 s
LD T11
RST Y11

END
