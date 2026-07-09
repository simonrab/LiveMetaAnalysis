"""Landscape service: the shared core behind the REST and MCP surfaces.

Ties the pieces together — deterministic CT.gov parsing, Claude free-text
ingest, dual-store persistence, reconciliation, and the evidence join — so the
API and MCP tools stay thin and can't diverge. CT.gov events are lazily seeded
on first request and cached (idempotent upsert), which also gives the as-of
time-slider data to work with offline.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from .ctgov_pipeline import study_to_events
from .ingest_llm import ingest_announcement
from .link import make_evidence_resolver
from .reconcile import assemble_landscape
from .schema import DevelopmentEvent, Landscape


def slugify(condition: str) -> str:
    """A stable landscape id for a condition (the events/links partition key)."""
    slug = re.sub(r"[^a-z0-9]+", "-", condition.lower()).strip("-")
    return slug or "landscape"


def _ctgov_events(search_pipeline: Callable[[str], list[dict]], condition: str) -> list[DevelopmentEvent]:
    events: list[DevelopmentEvent] = []
    for study in search_pipeline(condition):
        events.extend(study_to_events(study))
    return events


def get_landscape(
    store,
    condition: str,
    as_of: str | None = None,
    search_pipeline: Callable[[str], list[dict]] | None = None,
) -> Landscape:
    """Assemble the competitive matrix for a condition, as of a date.

    Seeds CT.gov-derived events into the store on first access (when a search
    function is supplied and nothing is stored yet), then assembles from the
    stored events + any ingested announcements + the evidence links.
    """
    lid = slugify(condition)
    events = store.load_events(lid)
    if not events and search_pipeline is not None:
        fresh = _ctgov_events(search_pipeline, condition)
        if fresh:
            store.save_events(lid, fresh)
            events = store.load_events(lid)

    links = store.load_links(lid)
    resolver = make_evidence_resolver(store)
    return assemble_landscape(
        events, as_of, links, evidence_for=resolver, condition=condition
    )


def ingest_to_landscape(
    store, condition: str, text: str, source_label: str, llm_client=None
) -> list[DevelopmentEvent]:
    """Ingest a free-text announcement/filing and persist any events found."""
    new = ingest_announcement(text, source_label, llm_client=llm_client)
    if new:
        store.save_events(slugify(condition), new)
    return new


def link_review(
    store, condition: str, asset_name: str, indication: str, question_id: str
) -> None:
    """Attach a saved review to an asset×indication cell (fuels the evidence badge)."""
    store.save_link(slugify(condition), asset_name, indication, question_id)


def asset_timeline(store, condition: str, name: str) -> list[DevelopmentEvent]:
    """One asset's dated event history, for the drill-in."""
    lid = slugify(condition)
    return [e for e in store.load_events(lid) if e.asset_name.lower() == name.lower()]
