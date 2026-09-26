; ST30 - HV insulation (HiPot) test, SAFETY-classified station (FX5U program block ST30_HIPOT)
; Rungs that drive SAFETY outputs are locked against AI edits.

# HiPot start permissive (SAFETY)
LD X33 ; ZS-3001 pallet in ST30
AND X32 ; ZS-3002 guard door closed (SAFETY)
AND X0 ; ES-0001 E-stop circuit healthy (SAFETY)
ANI M310
ANI M311
OUT Y30 ; HP-3005 HiPot start, HV enable (SAFETY)
OUT Y31 ; HL-3006 HV-on beacon (SAFETY)

# Tester result
LD X30 ; HP-3003 tester PASS
SET M310 ; HiPot PASS
LD X31 ; HP-3004 tester FAIL
SET M311 ; HiPot FAIL

# Reset results when the pallet leaves
LDF X33
RST M310
RST M311

END
