"""Side-by-side asset profile — operational facts compared, efficacy abstained.

Safety-critical. Two assets' pooled estimates come from *separate* meta-analyses
(different trials, comparators, populations, outcomes), so ranking them is a naive
indirect comparison the Cochrane method forbids. This module therefore:

- compares only **operational** attributes (phase, pivotal trial, enrollment,
  geography, next readout), and
- presents each asset's evidence **in its own context**, gated by a deterministic
  `assess_comparability` verdict that is almost always "not directly comparable" —
  so the UI shows a caveat banner, never a shared axis or a "winner".

Abstaining from the efficacy verdict is the trust story, not a limitation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from datetime import date

from .link import plain_evidence
from .schema import (
    AssetComparison,
    AssetDossier,
    AssetEvidenceContext,
    Comparability,
    ComparisonRow,
    Phase,
    TrialDetail,
    phase_rank,
)

_RATIO_MEASURES = {"HR", "RR", "OR"}


def _today() -> str:
    return date.today().isoformat()


def _phase_label(phase: Phase) -> str:
    return phase.value.replace("_", " ").title()


def assess_comparability(a: AssetEvidenceContext, b: AssetEvidenceContext) -> Comparability:
    """The gate. Two estimates are directly comparable only when they share an
    outcome measure, a population, AND a common comparator (an anchored indirect
    comparison). Across independent meta-analyses that essentially never holds, so
    the honest default is "not comparable", with the specific reasons surfaced."""
    reasons: list[str] = []

    if a.badge is None or b.badge is None:
        reasons.append("one or both assets have no committed pooled estimate")
    else:
        if a.badge.state != "pooled" or b.badge.state != "pooled":
            reasons.append("one or both estimates are not a committed pool")
        if a.badge.measure != b.badge.measure:
            reasons.append(
                f"different outcome measures ({a.badge.measure} vs {b.badge.measure})"
            )

    if a.population and b.population and a.population != b.population:
        reasons.append("different trial populations")

    # The comparator is the anchor for any valid indirect comparison; we do not
    # establish a common one, so the comparison stays unanchored.
    if not (a.comparator and b.comparator and a.comparator == b.comparator):
        reasons.append("no common comparator established (unanchored indirect comparison)")

    return Comparability(directly_comparable=not reasons, reasons=reasons)


def _primary_indication(dossier: AssetDossier, indication: str | None) -> str:
    if indication:
        return indication
    counts = Counter(t.indication for t in dossier.trials if t.indication)
    return counts.most_common(1)[0][0] if counts else ""


def _lead_phase(trials: Sequence[TrialDetail]) -> Phase:
    return max((t.phase for t in trials), key=phase_rank, default=Phase.UNKNOWN)


def _pivotal(trials: Sequence[TrialDetail]) -> TrialDetail | None:
    dated = list(trials)
    return max(dated, key=lambda t: (t.enrollment or 0, t.nct_id)) if dated else None


def _max_enrollment(trials: Sequence[TrialDetail]) -> int | None:
    vals = [t.enrollment for t in trials if t.enrollment]
    return max(vals) if vals else None


def _next_readout(trials: Sequence[TrialDetail], today: str) -> str | None:
    future = [
        t.primary_completion_date
        for t in trials
        if t.primary_completion_date and not t.has_results and t.primary_completion_date > today
    ]
    return min(future) if future else None


def _numeric_row(label: str, raw: list[int | None], render: Callable[[int], str]) -> ComparisonRow:
    """A count row with a neutral 'more' marker on the leader (facts, not effect claims)."""
    present = [v for v in raw if v]
    top = max(present) if present else None
    distinct = len(set(present)) > 1
    return ComparisonRow(
        label=label,
        values=[render(v) if v else "—" for v in raw],
        more=[bool(distinct and v is not None and v == top) for v in raw],
    )


def compare_assets(
    store,
    assets: list[str],
    indication: str | None = None,
    *,
    search: Callable[[str], list[dict]] | None = None,
    openfda=None,
    llm_client=None,
    as_of: str | None = None,
) -> AssetComparison:
    """Build the side-by-side profile for two or more assets."""
    from .service import _dossier_evidence_resolver, asset_dossier

    today = (as_of or _today())[:10]
    resolve = _dossier_evidence_resolver(store)
    notes: list[str] = []

    dossiers: dict[str, AssetDossier] = {}
    for asset in assets:
        dossiers[asset] = asset_dossier(
            store, asset, search=search, openfda=openfda, llm_client=llm_client
        )

    inds = {a: _primary_indication(d, indication) for a, d in dossiers.items()}

    # Operational rows — safe to compare.
    trials_by_asset = {a: d.trials for a, d in dossiers.items()}
    rows: list[ComparisonRow] = [
        ComparisonRow(label="Indication", values=[inds[a] or "—" for a in assets]),
        ComparisonRow(
            label="Lead phase", values=[_phase_label(_lead_phase(trials_by_asset[a])) for a in assets]
        ),
        ComparisonRow(
            label="Pivotal trial",
            values=[(_pivotal(trials_by_asset[a]).title if _pivotal(trials_by_asset[a]) else "—")
                    for a in assets],
        ),
        _numeric_row("Enrollment", [_max_enrollment(trials_by_asset[a]) for a in assets],
                     lambda v: f"{v:,}"),
        _numeric_row("Geography", [len(dossiers[a].countries) for a in assets],
                     lambda v: f"{v} countries"),
        ComparisonRow(
            label="Next readout",
            values=[(_next_readout(trials_by_asset[a], today) or "—") for a in assets],
        ),
    ]

    # Evidence — each in its own context, never a comparison row.
    evidence: list[AssetEvidenceContext] = []
    for asset in assets:
        ind = inds[asset]
        badge = resolve(asset, ind) if ind else None
        population = next((g.label for g in dossiers[asset].sub_indications), ind)
        evidence.append(
            AssetEvidenceContext(
                asset_name=asset,
                indication=ind,
                population=population,
                comparator=None,  # not extracted — keeps the comparison honestly unanchored
                plain_summary=plain_evidence(badge),
                badge=badge,
            )
        )

    comparability = (
        assess_comparability(evidence[0], evidence[1])
        if len(evidence) >= 2
        else Comparability(directly_comparable=False, reasons=["need at least two assets"])
    )

    return AssetComparison(
        assets=assets,
        indication=indication,
        rows=rows,
        evidence=evidence,
        comparability=comparability,
        notes=notes,
    )
