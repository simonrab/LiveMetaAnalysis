"""Rare-event pooling: Peto one-step odds ratio.

Inverse-variance and DerSimonian-Laird are biased when events are rare or arms
have zero cells (Cochrane Handbook v6.5, 10.4.4). Below ~1% event rates, or with
many zero-cell arms, switch to Peto or Mantel-Haenszel *without* a zero-cell
correction, and exclude studies with no events in either arm rather than nudging
them with a silent 0.5 continuity correction, which biases the estimate.

Peto is a fixed-effect method with a closed form, so it lives here in pure Python
rather than the REML engine. Effect is a log odds ratio.
"""

from __future__ import annotations

from collections.abc import Sequence

import math

from ..schema import (
    BinaryEffect,
    CIMethod,
    EffectMeasure,
    PoolMethod,
    PoolResult,
    StudyResult,
)

_Z = 1.959963984540054  # qnorm(0.975)


def event_rate(effects: Sequence[BinaryEffect]) -> float:
    """Overall event rate across both arms of all studies."""
    events = sum(e.treatment.events + e.control.events for e in effects)
    total = sum(e.treatment.total + e.control.total for e in effects)
    return events / total if total else 0.0


def _has_zero_cell(e: BinaryEffect) -> bool:
    a, c = e.treatment.events, e.control.events
    b = e.treatment.total - a
    d = e.control.total - c
    return 0 in (a, b, c, d)


def is_rare(effects: Sequence[BinaryEffect], threshold: float = 0.01) -> bool:
    """True when events are sparse enough that inverse-variance is unreliable.

    Triggered by a low overall event rate or by any zero-cell arm.
    """
    if not effects:
        return False
    if event_rate(effects) < threshold:
        return True
    return any(_has_zero_cell(e) for e in effects)


def pool_peto(
    effects: Sequence[BinaryEffect], measure: EffectMeasure = EffectMeasure.OR
) -> PoolResult:
    """Peto one-step odds-ratio pool. Fixed-effect; excludes double-zero studies."""
    notes: list[str] = []
    included: list[BinaryEffect] = []
    for e in effects:
        if e.treatment.events == 0 and e.control.events == 0:
            notes.append(f"{e.label}: no events in either arm — excluded (no 0.5 correction).")
            continue
        included.append(e)

    if len(included) < 2:
        raise ValueError("Peto pooling requires at least two informative studies")

    studies_out: list[StudyResult] = []
    sum_oe = 0.0
    sum_v = 0.0
    for e in included:
        a, n1 = e.treatment.events, e.treatment.total
        c, n2 = e.control.events, e.control.total
        n = n1 + n2
        e1 = a + c  # total events
        expected = n1 * e1 / n
        oe = a - expected
        v = (n1 * n2 * e1 * (n - e1)) / (n * n * (n - 1))
        sum_oe += oe
        sum_v += v

        yi = oe / v if v else 0.0
        vi = 1.0 / v if v else float("inf")
        studies_out.append(
            StudyResult(
                study_id=e.study_id,
                label=e.label,
                yi=yi,
                vi=vi,
                effect=math.exp(yi),
                ci_low=math.exp(yi - _Z * math.sqrt(vi)),
                ci_high=math.exp(yi + _Z * math.sqrt(vi)),
                weight=0.0,  # filled in below (weight ~ V_i)
            )
        )

    for s, e in zip(studies_out, included):
        # Peto weights are the per-study V_i; report as percent of the total.
        s.weight = 100.0 * (1.0 / s.vi) / sum_v if s.vi else 0.0

    est_log = sum_oe / sum_v
    se_log = math.sqrt(1.0 / sum_v)
    lb_log = est_log - _Z * se_log
    ub_log = est_log + _Z * se_log

    notes.append("Rare events — pooled with the Peto one-step odds ratio (fixed effect).")

    return PoolResult(
        measure=measure,
        model="fixed",
        method="Peto",
        pool_method=PoolMethod.PETO,
        engine="python",
        k=len(included),
        estimate=math.exp(est_log),
        ci_low=math.exp(lb_log),
        ci_high=math.exp(ub_log),
        ci_method=CIMethod.WALD,
        estimate_log=est_log,
        se_log=se_log,
        ci_low_log=lb_log,
        ci_high_log=ub_log,
        tau2=0.0,
        i2=0.0,
        q=0.0,
        q_p=1.0,
        studies=studies_out,
        notes=notes,
    )
