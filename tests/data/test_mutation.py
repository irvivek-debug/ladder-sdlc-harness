import pytest

from ladder_harness.scenarios.mutation import mutants, score
from ladder_harness.scenarios.runner import load_station_suites

from .test_cell_data import CELL


def test_mutant_generation_covers_every_operator():
    muts, invalid = mutants(CELL.golden("ST20"))
    assert {m.operator for m in muts} >= {"NEG", "DROP", "PRESET", "SETRST", "CMP", "EDGE", "TIMER"}
    assert len(muts) > 100 and invalid == 0


@pytest.mark.slow
def test_st20_mutation_score_at_least_90pct():
    report = score(CELL.golden("ST20"), load_station_suites(CELL.data_dir, "ST20"), processes=8)
    assert report.score >= 0.90, report.summary()
