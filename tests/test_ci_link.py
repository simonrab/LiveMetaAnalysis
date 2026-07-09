"""Evidence join: a review's latest state -> a landscape cell badge.

Measure-aware (ratio null=1, MD/SMD null=0) and gate-aware (pooled / gate_open /
abstained), so a competitive cell never shows a fabricated number.
"""

from livemeta.core.ci.link import badge_from_result, make_evidence_resolver
from livemeta.core.schema import (
    CIMethod,
    DiversityAssessment,
    EffectMeasure,
    GradeAssessment,
    GradeRating,
    PICO,
    PoolResult,
    Question,
    ReviewResult,
)
from livemeta.core.store import SnapshotStore


def _question(measure=EffectMeasure.HR, qid="q1"):
    return Question(
        id=qid,
        text="does X help",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=measure,
    )


def _pool(measure, estimate, ci_low, ci_high, k=6):
    import math

    return PoolResult(
        measure=measure,
        engine="python",
        k=k,
        estimate=estimate,
        ci_low=ci_low,
        ci_high=ci_high,
        ci_method=CIMethod.WALD,
        estimate_log=math.log(estimate) if estimate > 0 else estimate,
        se_log=0.05,
        ci_low_log=0.0,
        ci_high_log=0.0,
        tau2=0.0,
        i2=10.0,
        q=1.0,
        q_p=0.9,
    )


def _result(measure, pool=None, diversity=None, grade=None, qid="q1"):
    return ReviewResult(
        question=_question(measure, qid),
        pool=pool,
        diversity=diversity,
        grade=grade,
    )


def test_pooled_ratio_significant_reduction():
    r = _result(
        EffectMeasure.HR,
        pool=_pool(EffectMeasure.HR, 0.86, 0.79, 0.93),
        grade=GradeAssessment(outcome="MACE", certainty=GradeRating.MODERATE),
    )
    badge = badge_from_result("q1", r, version=3)
    assert badge.state == "pooled"
    assert badge.estimate == 0.86
    assert badge.grade_certainty == "moderate"
    assert badge.conclusion == "significant reduction"
    assert badge.version == 3


def test_pooled_ratio_crossing_one_is_not_significant():
    r = _result(EffectMeasure.HR, pool=_pool(EffectMeasure.HR, 0.95, 0.80, 1.12))
    assert badge_from_result("q1", r, None).conclusion == "no significant difference"


def test_md_uses_zero_as_the_null():
    sig = _result(EffectMeasure.MD, pool=_pool(EffectMeasure.MD, -2.0, -3.0, -1.0))
    assert badge_from_result("q1", sig, None).conclusion == "significant reduction"

    ns = _result(EffectMeasure.MD, pool=_pool(EffectMeasure.MD, 1.0, -1.0, 3.0))
    assert badge_from_result("q1", ns, None).conclusion == "no significant difference"


def test_gate_open_when_pool_withheld_pending_confirmation():
    diversity = DiversityAssessment(
        i2=82.0, i2_band="substantial", requires_confirmation=True, confirmed=False
    )
    r = _result(EffectMeasure.HR, pool=None, diversity=diversity)
    badge = badge_from_result("q1", r, None)
    assert badge.state == "gate_open"
    assert badge.estimate is None


def test_abstained_when_no_pool_and_no_gate():
    r = _result(EffectMeasure.HR, pool=None, diversity=None)
    assert badge_from_result("q1", r, None).state == "abstained"


def test_resolver_reads_latest_snapshot_from_store(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    store.save_snapshot(
        _result(EffectMeasure.HR, pool=_pool(EffectMeasure.HR, 0.86, 0.79, 0.93))
    )
    resolver = make_evidence_resolver(store)
    badge = resolver("q1")
    assert badge is not None and badge.state == "pooled" and badge.version == 1
    assert resolver("nonexistent") is None
