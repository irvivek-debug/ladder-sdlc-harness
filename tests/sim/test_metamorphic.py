import itertools
import random

from hypothesis import given, settings
from hypothesis import strategies as st

from ladder_harness.melsec.program import parse_il
from ladder_harness.sim.engine import Plc
from strategies import program_text, rung_lines


def outputs_for(text, combos, device="Y0"):
    p = Plc(parse_il(text))
    out = []
    for bits in combos:
        for i, b in enumerate(bits):
            p.set_bit(f"X{i}", b)
        p.scan()
        out.append(p.bit(device))
    return out


def test_de_morgan_rewrites_are_equivalent():
    combos = list(itertools.product([False, True], repeat=2))
    assert outputs_for("LDI X0\nANI X1\nOUT Y0\nEND\n", combos) == \
        outputs_for("LD X0\nOR X1\nINV\nOUT Y0\nEND\n", combos)
    assert outputs_for("LDI X0\nORI X1\nOUT Y0\nEND\n", combos) == \
        outputs_for("LD X0\nAND X1\nINV\nOUT Y0\nEND\n", combos)


A_IN = tuple(f"X{n:o}" for n in range(4))
B_IN = tuple(f"X{n:o}" for n in range(4, 8))


@settings(max_examples=150, deadline=None)
@given(rung_lines(inputs=A_IN, outputs=("Y0", "M0", "M1"), timers=(0,)),
       rung_lines(inputs=B_IN, outputs=("Y4", "M4", "M5"), timers=(4,)),
       st.integers(0, 2**32 - 1))
def test_independent_rungs_commute(ra, rb, seed):
    rng = random.Random(seed)
    stimuli = [[rng.random() < 0.5 for _ in range(8)] for _ in range(40)]

    def run(text):
        p = Plc(parse_il(text))
        for bits in stimuli:
            for i, b in enumerate(bits):
                p.set_bit(f"X{i:o}", b)
            p.scan()
        return p.snapshot()

    assert run("\n".join(ra + rb) + "\nEND\n") == run("\n".join(rb + ra) + "\nEND\n")


@settings(max_examples=100, deadline=None)
@given(program_text(), st.integers(0, 2**32 - 1))
def test_simulation_is_deterministic(case, seed):
    text, _ = case

    def run():
        rng = random.Random(seed)
        p = Plc(parse_il(text))
        for _ in range(60):
            p.set_bit(f"X{rng.randrange(8):o}", rng.random() < 0.5)
            p.scan()
        return p.snapshot()

    assert run() == run()
