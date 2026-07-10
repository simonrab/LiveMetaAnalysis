"""Pure text renderers for the CLI: report, ASCII forest plot, tables, diff.

Every function here takes Pydantic models and returns a `str` — no I/O, no
argparse, no store. That keeps them trivially testable (this is the trust-story
unit) and lets the same `PoolResult` feed both the terminal forest plot here and
the matplotlib PNG in `plot.py`. The ASCII forest mirrors the axis logic in
`web/src/components/ForestPlot.tsx` so the terminal and the web agree.
"""

from __future__ import annotations

import math

from ..core.pipeline import interpret_i2
from ..core.schema import (
    RATIO_MEASURES,
    PipelineEvent,
    PoolResult,
    ReviewDiff,
    ReviewResult,
    ReviewSummary,
    RobJudgment,
    SnapshotMeta,
    TrialCandidate,
)

_RULE = "─" * 72


def progress_line(event: PipelineEvent) -> str:
    """A single streamed pipeline step, e.g. `[extract] LEADER: HR 0.87`."""
    return f"[{event.stage}] {event.message}"


# --- ASCII forest plot ------------------------------------------------------


def _weight_glyph(weight: float) -> str:
    """A point marker whose weight echoes the weight-sized square in the web plot."""
    if weight >= 20:
        return "#"
    if weight >= 12:
        return "O"
    if weight >= 6:
        return "o"
    return "·"


def forest_ascii(
    pool: PoolResult,
    *,
    width: int = 72,
    highlight: frozenset[str] | set[str] = frozenset(),
) -> str:
    """A terminal forest plot from `pool.studies`, mirroring ForestPlot.tsx.

    Ratio measures (RR/OR/HR) use a log axis with the no-effect reference at 1;
    continuous measures (MD/SMD) use a linear axis centred on 0. One row per
    study (CI band, weight-sized point marker, effect annotation), a pooled
    diamond row, and an axis footer. Highlighted study ids (a newly injected
    trial) are tagged `NEW`.
    """
    rows = pool.studies
    ratio = pool.measure in RATIO_MEASURES
    nul = 1.0 if ratio else 0.0
    highlight = set(highlight)

    label_w = max([len("Pooled (RE)")] + [len(r.study_id) for r in rows]) + 1
    band_w = max(20, width - label_w - 26)

    lows = [r.ci_low for r in rows] + [pool.ci_low]
    highs = [r.ci_high for r in rows] + [pool.ci_high]

    if ratio:
        lo_dom = min(lows + [0.5])
        hi_dom = max(highs + [2.0])
        project = math.log
    else:
        span = max([abs(v) for v in highs + lows] + [1.0])
        lo_dom = min(lows + [-span])
        hi_dom = max(highs + [span])

        def project(v: float) -> float:
            return v

    s_min = project(lo_dom)
    s_max = project(hi_dom)
    span_s = (s_max - s_min) or 1.0

    def col(v: float) -> int:
        c = round((project(v) - s_min) / span_s * (band_w - 1))
        return max(0, min(band_w - 1, c))

    ref_col = col(nul)

    def study_row(label, lo, eff, hi, glyph, is_new) -> str:
        band = [" "] * band_w
        band[ref_col] = "|"
        for c in range(col(lo), col(hi) + 1):
            if band[c] == " ":
                band[c] = "-"
        band[col(eff)] = "*" if is_new else glyph
        tag = " NEW" if is_new else ""
        ann = f"{eff:.2f} [{lo:.2f}, {hi:.2f}]"
        return f"{label:<{label_w}}{''.join(band)}  {ann}{tag}"

    lines: list[str] = []
    for r in rows:
        lines.append(
            study_row(
                r.study_id, r.ci_low, r.effect, r.ci_high,
                _weight_glyph(r.weight), r.study_id in highlight,
            )
        )

    # Pooled diamond row: <===> spanning the CI, centred on the estimate.
    band = [" "] * band_w
    band[ref_col] = "|"
    lo_c, hi_c, mid_c = col(pool.ci_low), col(pool.ci_high), col(pool.estimate)
    for c in range(lo_c, hi_c + 1):
        band[c] = "="
    band[lo_c] = "<"
    band[hi_c] = ">"
    band[mid_c] = "#"
    pooled_ann = f"{pool.estimate:.2f} [{pool.ci_low:.2f}, {pool.ci_high:.2f}]"
    lines.append(f"{'Pooled (RE)':<{label_w}}{''.join(band)}  {pooled_ann}")

    # Axis footer: a caret under the no-effect reference, then its value + hints.
    axis = [" "] * band_w
    axis[ref_col] = "^"
    lines.append(f"{'':<{label_w}}{''.join(axis)}")
    lines.append(
        f"{'':<{label_w}}no effect = {nul:g}"
        "   (<- favors intervention | favors comparator ->)"
    )
    return "\n".join(lines)


# --- report -----------------------------------------------------------------


def _rob_line(result: ReviewResult) -> str:
    if not result.rob:
        return "Risk of bias: not assessed."
    pending = sum(1 for r in result.rob if r.overall == RobJudgment.PENDING)
    if pending == len(result.rob):
        return (
            "Risk of bias: PENDING for all trials "
            "(no ANTHROPIC_API_KEY — RoB 2 appraisal not run, not fabricated)."
        )
    counts: dict[str, int] = {}
    for r in result.rob:
        counts[r.overall.value] = counts.get(r.overall.value, 0) + 1
    summary = ", ".join(f"{n} {k.replace('_', ' ')}" for k, n in sorted(counts.items()))
    suffix = f" ({pending} PENDING — no model key)" if pending else ""
    return f"Risk of bias (RoB 2): {summary}{suffix}."


def _grade_line(result: ReviewResult) -> str:
    if result.grade is None:
        return "GRADE certainty: not assessed."
    return f"GRADE certainty: {result.grade.certainty.value.replace('_', ' ')}."


def _diversity_line(result: ReviewResult) -> str | None:
    d = result.diversity
    if d is None:
        return None
    if not d.clinical_assessed:
        return (
            "Homogeneity: assessed on I² alone (clinical-diversity read not run "
            "— no model key)."
        )
    return f"Homogeneity: {d.rationale}" if d.rationale else None


def report_text(result: ReviewResult) -> str:
    """The full human-readable report for one review: header, pooled estimate,
    heterogeneity, ASCII forest, appraisal lines, and provenance-honest caveats.
    """
    q = result.question
    lines: list[str] = [_RULE, f"Living meta-analysis — {q.id}", _RULE, q.text, ""]

    lines.append(f"Population:   {q.pico.population}")
    lines.append(f"Intervention: {q.pico.intervention}")
    lines.append(f"Comparator:   {q.pico.comparator}")
    lines.append(f"Outcome:      {q.pico.outcome}")
    lines.append(f"Measure:      {q.measure.value}")
    lines.append("")

    pool = result.pool
    if pool is None:
        lines.append("RESULT: abstained — too few valid trials to pool.")
        if result.summary:
            lines.append(result.summary)
        div = _diversity_line(result)
        if div:
            lines.append(div)
        n_flagged = sum(1 for v in result.validations if not v.passed)
        lines.append(
            f"Extractions: {len(result.extractions)} trials, "
            f"{n_flagged} flagged at the validation gate."
        )
        lines.append(_RULE)
        return "\n".join(lines)

    ci_kind = "Hartung-Knapp" if pool.ci_method.value == "hksj" else "Wald"
    lines.append(
        f"POOLED ESTIMATE ({pool.k} trials, random-effects {pool.method}, "
        f"{pool.engine}):"
    )
    lines.append(
        f"  {pool.measure.value} {pool.estimate:.2f}  "
        f"95% CI {pool.ci_low:.2f} to {pool.ci_high:.2f}  ({ci_kind})"
    )
    lines.append(
        f"  Heterogeneity: I² = {pool.i2:.0f}% ({interpret_i2(pool.i2)}), "
        f"τ² = {pool.tau2:.3f}, Q p = {pool.q_p:.3f}"
    )
    if pool.prediction_low is not None and pool.prediction_high is not None:
        lines.append(
            f"  Prediction interval: {pool.prediction_low:.2f} to "
            f"{pool.prediction_high:.2f}"
        )
    lines.append("")

    lines.append("FOREST PLOT")
    lines.append(forest_ascii(pool))
    lines.append("")

    if result.summary:
        lines.append("SUMMARY")
        lines.append(result.summary)
        lines.append("")

    lines.append("APPRAISAL")
    lines.append(f"  {_rob_line(result)}")
    lines.append(f"  {_grade_line(result)}")
    div = _diversity_line(result)
    if div:
        lines.append(f"  {div}")
    if result.sensitivity:
        lines.append(
            f"  Leave-one-out sensitivity: {len(result.sensitivity)} rows "
            "(no single trial drives the result unless flagged)."
        )
    lines.append(_RULE)
    return "\n".join(lines)


# --- diff -------------------------------------------------------------------


def diff_block(diff: ReviewDiff, status: str) -> str:
    """Render a living-update diff: trial counts, estimate move, conclusion status."""
    lines = [_RULE, f"LIVING UPDATE — {diff.question_id}", _RULE]
    lines.append(
        f"Version {diff.previous_version} -> {diff.current_version}   "
        f"pooled trials {diff.k_prev} -> {diff.k_curr}"
    )
    if diff.added_trials:
        lines.append(f"Added: {', '.join(diff.added_trials)}")
    if diff.estimate_prev is not None and diff.estimate_curr is not None:
        delta = diff.delta if diff.delta is not None else 0.0
        lines.append(
            f"Estimate {diff.estimate_prev:.2f} -> {diff.estimate_curr:.2f} "
            f"(Δ {delta:+.2f})"
        )
    lines.append(f"Status: {status}")
    if status == "conclusion-moved":
        flips = []
        if diff.significance_changed:
            flips.append("statistical significance flipped")
        if diff.direction_changed:
            flips.append("direction of effect flipped")
        if flips:
            lines.append("  " + "; ".join(flips))
    for note in diff.notes:
        lines.append(f"  note: {note}")
    lines.append(_RULE)
    return "\n".join(lines)


# --- tables -----------------------------------------------------------------


def history_table(snapshots: list[SnapshotMeta]) -> str:
    if not snapshots:
        return "No versions found."
    lines = [f"{'VER':>3}  {'CREATED':<25}  {'K':>3}  {'ESTIMATE':>18}"]
    for s in snapshots:
        est = (
            f"{s.measure} {s.estimate:.2f}" if s.estimate is not None else "—"
        )
        lines.append(f"{s.version:>3}  {s.created_at:<25}  {s.k:>3}  {est:>18}")
    return "\n".join(lines)


def candidates_table(candidates: list[TrialCandidate]) -> str:
    if not candidates:
        return "No new trials found."
    lines = [f"{'NCT':<14}  {'SOURCE':<16}  TITLE"]
    for c in candidates:
        lines.append(f"{c.nct_id:<14}  {c.source:<16}  {c.title}")
    return "\n".join(lines)


def reviews_table(summaries: list[ReviewSummary]) -> str:
    if not summaries:
        return "No saved reviews."
    lines = [f"{'QUESTION':<18}  {'VER':>3}  {'K':>3}  {'ESTIMATE':>18}  STATUS"]
    for s in summaries:
        est = (
            f"{s.measure} {s.estimate:.2f} [{s.ci_low:.2f},{s.ci_high:.2f}]"
            if s.estimate is not None and s.ci_low is not None and s.ci_high is not None
            else "—"
        )
        lines.append(
            f"{s.question_id:<18}  {s.versions:>3}  {s.k:>3}  {est:>18}  {s.status}"
        )
    return "\n".join(lines)
