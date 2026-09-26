from hypothesis import given, settings

from ladder_harness.melsec.program import format_il, parse_il
from strategies import program_text


@settings(max_examples=300, deadline=None)
@given(program_text())
def test_segmentation_recovers_generated_rungs(case):
    text, n = case
    assert len(parse_il(text).rungs) == n + 1  # + END


@settings(max_examples=300, deadline=None)
@given(program_text())
def test_print_parse_round_trip(case):
    text, _ = case
    p = parse_il(text)
    canonical = format_il(p)
    assert parse_il(canonical) == p
    assert format_il(parse_il(canonical)) == canonical
