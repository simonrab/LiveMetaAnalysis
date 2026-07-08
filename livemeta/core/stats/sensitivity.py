"""Leave-one-out sensitivity analysis.

Re-runs the validated pool k times, each omitting one study, so a reviewer can
see whether the pooled estimate rests on any single trial. This is a robustness
*view* over the engine — it never re-implements pooling, it only calls it.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..schema import BinaryEffect, EffectMeasure, EffectPoint, LeaveOneOutRow
from . import engine as stats_engine


def _identity(study: BinaryEffect | EffectPoint) -> tuple[str, str]:
    return study.study_id, study.label


def leave_one_out(
    studies: Sequence[BinaryEffect | EffectPoint],
    measure: EffectMeasure = EffectMeasure.RR,
    method: str = "REML",
) -> list[LeaveOneOutRow]:
    """Pool the studies k times, each time leaving one out.

    Returns one row per omitted study. Needs at least three studies: with two,
    omitting one leaves a single study, which cannot be pooled — we return an
    empty list rather than fabricate a result.
    """
    studies = list(studies)
    if len(studies) < 3:
        return []

    rows: list[LeaveOneOutRow] = []
    for i, omitted in enumerate(studies):
        subset = studies[:i] + studies[i + 1 :]
        sub = stats_engine.pool(subset, measure=measure, method=method)
        sid, label = _identity(omitted)
        rows.append(
            LeaveOneOutRow(
                omitted_study_id=sid,
                omitted_label=label,
                k=sub.k,
                estimate=sub.estimate,
                ci_low=sub.ci_low,
                ci_high=sub.ci_high,
                i2=sub.i2,
            )
        )
    return rows
