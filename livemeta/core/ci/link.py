"""Join a landscape cell to the living pooled evidence for its asset/outcome.

A linked cell shows the meta-analysis result as a denormalized `EvidenceBadge`.
Two properties keep it honest:

- **Measure-aware:** the linked review may be HR/RR/OR (null = 1) or MD/SMD
  (null = 0), so significance and direction are computed against the right null.
- **Gate-aware:** the pool can be committed, *withheld pending a homogeneity
  confirmation*, or an abstention — three distinct states, so a cell never shows
  a fabricated number.
"""

from __future__ import annotations

from collections.abc import Callable

from ..schema import ReviewResult
from .schema import EvidenceBadge

_RATIO_MEASURES = {"HR", "RR", "OR"}


def _conclusion(measure: str, estimate: float, ci_low: float, ci_high: float) -> str:
    """A measure-aware, human-readable verdict for the badge."""
    if measure in _RATIO_MEASURES:
        significant = ci_high < 1 or ci_low > 1
        direction = "reduction" if estimate < 1 else "increase" if estimate > 1 else "no change"
    else:  # MD / SMD — null effect is 0
        significant = ci_high < 0 or ci_low > 0
        direction = "reduction" if estimate < 0 else "increase" if estimate > 0 else "no change"
    return f"significant {direction}" if significant else "no significant difference"


def badge_from_result(
    question_id: str, result: ReviewResult, version: int | None
) -> EvidenceBadge:
    """Denormalize a review's latest state into a cell badge.

    Order matters: a committed pool wins; otherwise a homogeneity gate that is
    awaiting confirmation is reported as `gate_open`; otherwise the review
    abstained (too few trials / no poolable data).
    """
    measure = result.question.measure.value
    pool = result.pool

    if pool is not None:
        return EvidenceBadge(
            question_id=question_id,
            measure=measure,
            state="pooled",
            estimate=pool.estimate,
            ci_low=pool.ci_low,
            ci_high=pool.ci_high,
            grade_certainty=result.grade.certainty.value if result.grade else None,
            conclusion=_conclusion(measure, pool.estimate, pool.ci_low, pool.ci_high),
            version=version,
            k=pool.k,
        )

    diversity = result.diversity
    if diversity is not None and diversity.requires_confirmation and not diversity.confirmed:
        return EvidenceBadge(
            question_id=question_id,
            measure=measure,
            state="gate_open",
            conclusion="pooling withheld pending homogeneity confirmation",
            version=version,
        )

    return EvidenceBadge(
        question_id=question_id,
        measure=measure,
        state="abstained",
        conclusion="insufficient data to pool",
        version=version,
    )


def plain_evidence(badge: EvidenceBadge | None) -> str:
    """A jargon-free one-liner for the evidence state (recent copy direction).

    The HR/CI/GRADE detail stays on the badge for hover/drill-in; this is the
    headline the dense CI grids lead with.
    """
    if badge is None:
        return "no linked evidence"
    if badge.state == "gate_open":
        return "evidence pending review"
    if badge.state == "abstained":
        return "not enough data yet"
    # pooled — the conclusion string already reads "significant reduction" etc.
    conclusion = (badge.conclusion or "").lower()
    if "significant" in conclusion and "no significant" not in conclusion:
        return "benefit proven"
    return "no significant benefit"


def make_evidence_resolver(store) -> Callable[[str], EvidenceBadge | None]:
    """A resolver `question_id -> EvidenceBadge` backed by the snapshot store.

    Kept as a factory so reconciliation stays store-agnostic (it only calls the
    resolver). Returns None for an unknown review so the cell simply has no badge.
    """

    def evidence_for(question_id: str) -> EvidenceBadge | None:
        result = store.load_latest(question_id)
        if result is None:
            return None
        versions = store.list_versions(question_id)
        version = versions[-1] if versions else None
        return badge_from_result(question_id, result, version)

    return evidence_for
