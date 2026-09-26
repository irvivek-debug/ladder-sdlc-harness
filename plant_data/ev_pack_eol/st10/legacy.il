; ST10_CONVEYOR (FX5U) - converted from FX3U project CV_ST1_V2, 2019

LDI    X13
OUT    M191             ; ST10 motor overload alarm

LD     X1
RST    M190

LD     M190
OR     M191             ; ST10 motor overload alarm
ORI    X0               ; ES-0001 E-stop chain healthy
OUT    M199

LD     X2               ; SS-0003 auto mode
ANI    M199
OUT    Y10

LD     X10
OUT    M100             ; ST10 pallet in position

LDP    X14              ; RQ-1005 release request
SET    Y11              ; XY-1004 stopper release

LD     Y11              ; XY-1004 stopper release
OUT    T11 K20

LD     T11
RST    Y11              ; XY-1004 stopper release

END
