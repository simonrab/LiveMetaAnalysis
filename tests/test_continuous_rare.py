"""Continuous (MD/SMD) effect sizes and rare-event (Peto) pooling.

Expected values are hand-computed from the Cochrane Handbook v6.5 formulas
(Ch. 6 for effect sizes, Ch. 10.4 for rare events) and pinned here. These paths
are not on the GLP-1 HR demo route, so they are covered by unit tests only.
"""

import math

import pytest

from livemeta.core.schema import (
    BinaryArm,
    BinaryEffect,
    ContinuousArm,
    ContinuousEffect,
    EffectMeasure,
    PoolMethod,
)
from livemeta.core.stats import engine as stats_engine
from livemeta.core.stats import escalc
from livemeta.core.stats import rare_event


# --- Continuous effect sizes ------------------------------------------------

def _cont(m1, sd1, n1, m2, sd2, n2, sid="S"):
    return ContinuousEffect(
        study_id=sid,
        label=sid,
        treatment=ContinuousArm(mean=m1, sd=sd1, n=n1),
        control=ContinuousArm(mean=m2, sd=sd2, n=n2),
    )


def test_mean_difference_point():
    # MD = m1 - m2; var = sd1^2/n1 + sd2^2/n2.
    p = escalc.continuous_point(_cont(10, 2, 50, 8, 2.5, 50), EffectMeasure.MD)
    assert p.yi == pytest.approx(2.0, abs=1e-9)
    assert p.vi == pytest.approx(4 / 50 + 6.25 / 50, abs=1e-9)  # 0.205


def test_standardized_mean_difference_hedges_g():
    # Hedges' g with the small-sample correction, and its variance.
    p = escalc.continuous_point(_cont(10, 2, 50, 8, 2.5, 50), EffectMeasure.SMD)
    assert p.yi == pytest.approx(0.876674, abs=1e-4)
    assert p.vi == pytest.approx(0.043843, abs=1e-4)


def test_continuous_pool_stays_on_natural_scale():
    studies = [
        escalc.continuous_point(_cont(10, 2, 50, 8, 2.5, 50, "A"), EffectMeasure.MD),
        escalc.continuous_point(_cont(12, 3, 60, 9, 3, 60, "B"), EffectMeasure.MD),
    ]
    res = stats_engine.pool(studies, measure=EffectMeasure.MD)
    # MD is already on the natural scale — no exp() transform.
    assert res.estimate == pytest.approx(res.estimate_log, abs=1e-9)
    assert 2.0 < res.estimate < 3.0
    # Per-study forest rows also identity-scaled.
    for s in res.studies:
        assert s.effect == pytest.approx(s.yi, abs=1e-9)


# --- Rare events: Peto ------------------------------------------------------

def _bin(a, n1, c, n2, sid="S"):
    return BinaryEffect(
        study_id=sid,
        label=sid,
        treatment=BinaryArm(events=a, total=n1),
        control=BinaryArm(events=c, total=n2),
    )


# A sparse outcome with a zero cell — the case inverse-variance can't handle.
RARE = [_bin(0, 100, 3, 100, "R1"), _bin(2, 200, 4, 200, "R2")]


def test_is_rare_detects_low_event_rate():
    assert rare_event.is_rare(RARE) is True
    # A dense binary outcome is not rare.
    dense = [_bin(100, 1000, 120, 1000, "D1"), _bin(50, 500, 65, 500, "D2")]
    assert rare_event.is_rare(dense) is False


def test_peto_pooled_odds_ratio_matches_hand_computation():
    res = rare_event.pool_peto(RARE, measure=EffectMeasure.OR)
    assert res.pool_method == PoolMethod.PETO
    assert res.model == "fixed"
    assert res.k == 2
    # Hand-computed: sum(O-E) = -2.5, sum(V) = 2.223665 -> logOR = -1.124270.
    assert res.estimate_log == pytest.approx(-1.124270, abs=1e-4)
    assert res.estimate == pytest.approx(math.exp(-1.124270), abs=1e-4)
    assert res.ci_low == pytest.approx(math.exp(-2.438627), abs=1e-3)
    assert res.ci_high == pytest.approx(math.exp(0.190087), abs=1e-3)


def test_peto_excludes_double_zero_studies_without_correction():
    # A study with zero events in both arms carries no information — dropped,
    # and never nudged with a 0.5 continuity correction.
    with_double_zero = RARE + [_bin(0, 50, 0, 50, "Z")]
    res = rare_event.pool_peto(with_double_zero, measure=EffectMeasure.OR)
    assert res.k == 2  # the double-zero study was excluded
    assert any("excluded" in n.lower() for n in res.notes)


def test_pool_routes_rare_binary_to_peto():
    # The engine dispatches sparse binary tables to Peto rather than raising on
    # the zero-cell that inverse-variance can't handle.
    res = stats_engine.pool(RARE, measure=EffectMeasure.OR)
    assert res.pool_method == PoolMethod.PETO
