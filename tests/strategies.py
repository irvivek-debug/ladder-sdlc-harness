"""Hypothesis strategies that generate well-formed FX5 .il programs by construction."""
from hypothesis import strategies as st

INPUTS = [f"X{n:o}" for n in range(8)]
MEMS = [f"M{n}" for n in range(8)]
OUTPUTS = [f"Y{n:o}" for n in range(8)]
SAFE_TEXT = st.text(alphabet=st.characters(categories=("Lu", "Ll", "Nd"), include_characters=" -_"),
                    max_size=20).map(str.strip)


@st.composite
def expr_lines(draw, pool, depth=0):
    if depth >= 2 or draw(st.booleans()):
        lines = [f"{draw(st.sampled_from(['LD', 'LDI', 'LDP', 'LDF']))} {draw(st.sampled_from(pool))}"]
        for _ in range(draw(st.integers(0, 2))):
            lines.append(f"{draw(st.sampled_from(['AND', 'ANI', 'OR', 'ORI']))} {draw(st.sampled_from(pool))}")
        return lines
    left = draw(expr_lines(pool, depth + 1))
    right = draw(expr_lines(pool, depth + 1))
    return left + right + [draw(st.sampled_from(["ANB", "ORB"]))]


@st.composite
def rung_lines(draw, inputs=tuple(INPUTS + MEMS), outputs=tuple(OUTPUTS + MEMS), timers=(0, 1, 2, 3)):
    lines = draw(expr_lines(list(inputs)))
    lines.append(f"{draw(st.sampled_from(['OUT', 'SET', 'RST']))} {draw(st.sampled_from(list(outputs)))}")
    if timers and draw(st.booleans()):
        base = draw(st.sampled_from(["OUT", "OUTH", "OUTHS"]))
        lines.append(f"{base} T{draw(st.sampled_from(list(timers)))} K{draw(st.integers(1, 50))}")
    if draw(st.booleans()):
        comment = draw(SAFE_TEXT)
        if comment:
            lines[0] = f"{lines[0]} ; {comment}"
    return lines


@st.composite
def program_text(draw, max_rungs=6):
    rungs = draw(st.lists(rung_lines(), min_size=1, max_size=max_rungs))
    body = []
    for r in rungs:
        if draw(st.booleans()):
            stmt = draw(SAFE_TEXT)
            if stmt:
                body.append(f"# {stmt}")
        body.extend(r)
    return "\n".join(body) + "\nEND\n", len(rungs)
