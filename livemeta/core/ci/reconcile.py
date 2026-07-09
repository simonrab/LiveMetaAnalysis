"""Assemble dated development events into a competitive matrix, as of a date.

Deterministic and trust-bearing:
- Time-travel is a pure filter (`date <= as_of`); undated events are excluded
  once an as-of is set, because we cannot prove they had happened by then.
- The most advanced *sourced* stage wins (every event carries provenance).
- Conflicting sources are flagged, never silently resolved: if a source reports
  a lower stage at or after the date another source claims a higher one, that is
  a contradiction about the current state — surfaced, not picked.
"""

from __future__ import annotations

from collections.abc import Callable

from .schema import (
    DevelopmentEvent,
    EvidenceBadge,
    Landscape,
    LandscapeCell,
    Phase,
    phase_rank,
)

# A key that orders cells and time-filters events. Undated events sort first.
_MIN_DATE = ""


def _date_key(ev: DevelopmentEvent) -> str:
    return ev.date or _MIN_DATE


def _visible(events: list[DevelopmentEvent], as_of: str | None) -> list[DevelopmentEvent]:
    if as_of is None:
        return list(events)
    # A dated event counts only if it is on/before the as-of date; an undated
    # event is dropped because its timing cannot be placed.
    return [e for e in events if e.date is not None and e.date <= as_of]


def _detect_conflict(events: list[DevelopmentEvent], top: DevelopmentEvent) -> str | None:
    """Flag a source that reports a lower stage at/after the top stage's date."""
    top_rank = phase_rank(top.phase)
    top_date = top.date or _MIN_DATE
    for e in events:
        if e.source_type == top.source_type:
            continue
        if e.date is None:
            continue
        if e.date >= top_date and phase_rank(e.phase) < top_rank:
            return (
                f"{e.source_type.value} reports {e.phase.value} as of {e.date}, but "
                f"{top.source_type.value} reports {top.phase.value} "
                f"(as of {top.date or 'undated'})."
            )
    return None


def _build_cell(
    key: tuple[str, str, str | None],
    events: list[DevelopmentEvent],
    links: dict[tuple[str, str], str],
    evidence_for: Callable[[str], EvidenceBadge | None] | None,
) -> LandscapeCell:
    asset, indication, line = key
    # Most advanced sourced stage; ties broken by the later date.
    top = max(events, key=lambda e: (phase_rank(e.phase), _date_key(e)))
    latest = max(events, key=_date_key)
    conflict_note = _detect_conflict(events, top)

    question_id = links.get((asset, indication))
    badge = evidence_for(question_id) if (question_id and evidence_for) else None

    provenance = [p for e in events for p in e.provenance]
    return LandscapeCell(
        asset_name=asset,
        indication=indication,
        line_of_therapy=line,
        current_phase=top.phase,
        status=latest.status,
        sponsor=latest.sponsor or top.sponsor,
        sponsor_class=latest.sponsor_class or top.sponsor_class,
        latest_event=latest,
        conflict=conflict_note is not None,
        conflict_note=conflict_note,
        question_id=question_id,
        evidence=badge,
        provenance=provenance,
    )


def assemble_landscape(
    events: list[DevelopmentEvent],
    as_of: str | None,
    links: dict[tuple[str, str], str],
    evidence_for: Callable[[str], EvidenceBadge | None] | None = None,
    condition: str = "",
) -> Landscape:
    """Group events into asset × indication cells, reconciled as of `as_of`.

    `links` maps (asset, indication) → a saved review's `question_id`; when an
    `evidence_for` resolver is supplied, the linked cell gets a living evidence
    badge (see `link.py`). Reconciliation stays pure — the store is reached only
    through `evidence_for`.
    """
    groups: dict[tuple[str, str, str | None], list[DevelopmentEvent]] = {}
    for e in _visible(events, as_of):
        groups.setdefault((e.asset_name, e.indication, e.line_of_therapy), []).append(e)

    cells = [
        _build_cell(key, group, links, evidence_for)
        for key, group in groups.items()
        if group
    ]
    cells.sort(key=lambda c: (c.asset_name, c.indication))

    assets = sorted({c.asset_name for c in cells})
    indications = sorted({c.indication for c in cells})
    return Landscape(
        condition=condition,
        as_of=as_of,
        assets=assets,
        indications=indications,
        cells=cells,
    )
