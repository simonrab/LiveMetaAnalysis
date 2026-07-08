"""Leave-one-out sensitivity — a mandatory Cochrane robustness check.

Re-pools the k studies k times, each time omitting one, so a reviewer can see
whether any single trial is driving the pooled estimate. Pure reuse of the
validated engine: no new pooling math lives here.
"""

import pytest

from livemeta.core.schema import EffectMeasure
from livemeta.core.stats import engine as stats_engine
from livemeta.core.stats import escalc
from livemeta.core.stats import sensitivity

# The locked GLP-1 MACE demo, as in test_stats_engine.
GLP1_CVOTS = [
    ("ELIXA", 1.02, 0.89, 1.17),
    ("LEADER", 0.87, 0.78, 0.97),
    ("SUSTAIN-6", 0.74, 0.58, 0.95),
    ("EXSCEL", 0.91, 0.83, 1.00),
    ("Harmony", 0.78, 0.68, 0.90),
    ("REWIND", 0.88, 0.79, 0.99),
    ("PIONEER-6", 0.79, 0.57, 1.11),
    ("AMPLITUDE-O", 0.73, 0.58, 0.92),
]


def _glp1_points():
    return [escalc.ratio_ci_point(t, t, hr, lb, ub) for (t, hr, lb, ub) in GLP1_CVOTS]


def test_leave_one_out_drops_each_study_once():
    rows = sensitivity.leave_one_out(_glp1_points(), measure=EffectMeasure.HR)

    assert len(rows) == 8
    # Each row omits a distinct trial, and each sub-pool has k-1 = 7 studies.
    assert {r.omitted_study_id for r in rows} == {t for (t, *_ ) in GLP1_CVOTS}
    assert all(r.k == 7 for r in rows)
    # Labels are carried through for the UI.
    assert all(r.omitted_label for r in rows)


def test_leave_one_out_sub_pools_are_reasonable():
    full = stats_engine.pool(_glp1_points(), measure=EffectMeasure.HR)
    rows = sensitivity.leave_one_out(_glp1_points(), measure=EffectMeasure.HR)

    # No single omission moves the estimate far from the full pool (~0.86).
    for r in rows:
        assert 0.80 < r.estimate < 0.92
        assert r.ci_low < r.estimate < r.ci_high

    # Dropping ELIXA (the one null trial) should nudge the estimate down.
    elixa = next(r for r in rows if r.omitted_study_id == "ELIXA")
    assert elixa.estimate < full.estimate


def test_leave_one_out_guards_too_few_studies():
    # With only two studies, omitting one leaves a single study — not poolable.
    rows = sensitivity.leave_one_out(_glp1_points()[:2], measure=EffectMeasure.HR)
    assert rows == []
