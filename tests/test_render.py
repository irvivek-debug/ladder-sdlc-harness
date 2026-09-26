import xml.etree.ElementTree as ET

from ladder_harness.melsec.program import parse_il
from ladder_harness.render import diff_html, diff_programs, program_svg, rung_networks, rung_svg, unified_il_diff

P = parse_il("LD X0\nOR Y0\nLD X2\nOR X3\nANB\nANI X1\nOUT Y0\nOUT T0 K50\n"
             "LD X0\nMPS\nAND X1\nOUT Y1\nMPP\nAND> D100 K30\nINV\nOUT Y2\nEND\n")


def test_networks_share_condition_for_continuous_outputs():
    nets = rung_networks(P.rungs[0])
    assert len(nets) == 1 and [i.text() for i in nets[0][1]] == ["OUT Y0", "OUT T0 K50"]
    assert len(rung_networks(P.rungs[1])) == 2


def test_svg_is_well_formed_and_labelled():
    svg = program_svg(P, comments={"X0": "start <PB> & go"})
    ET.fromstring(svg)
    assert "X0" in svg and "start &lt;PB&gt; &amp; go" in svg and "T0" in svg and "D100" in svg


def test_rung_svg_highlight():
    svg = rung_svg(P.rungs[0], highlight=True)
    ET.fromstring(svg)
    assert "lad-hl" in svg


def test_diff_marks_changed_rung():
    new = parse_il("LD X0\nOR Y0\nLD X2\nOR X3\nANB\nOUT Y0\nOUT T0 K50\n"
                   "LD X0\nMPS\nAND X1\nOUT Y1\nMPP\nAND> D100 K30\nINV\nOUT Y2\nEND\n")
    kinds = [c.kind for c in diff_programs(P, new)]
    assert kinds.count("changed") == 1 and kinds.count("equal") == 2
    html = diff_html(P, new, title="t")
    assert "<svg" in html and "ANI" in unified_il_diff(P, new)


def test_added_and_removed_rungs():
    a = parse_il("LD X0\nOUT Y0\nLD X1\nOUT Y1\nEND\n")
    b = parse_il("LD X0\nOUT Y0\nLD X2\nOUT Y2\nLD X1\nOUT Y1\nEND\n")
    assert [c.kind for c in diff_programs(a, b)] == ["equal", "added", "equal", "equal"]
    assert [c.kind for c in diff_programs(b, a)] == ["equal", "removed", "equal", "equal"]
