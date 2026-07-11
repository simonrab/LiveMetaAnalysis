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

from .ctgov_pipeline import (
    _nct,
    study_to_events,
    study_to_trial_detail,
)
from .dossier import build_asset_dossier
from .indication import build_indication_map
from .ingest_llm import ingest_announcement
from .link import make_evidence_resolver
from .reconcile import assemble_landscape
from .schema import (
    AssetDossier,
    CompanyPipeline,
    DevelopmentEvent,
    EvidenceBadge,
    IndicationMap,
    Source,
    SourceSelection,
    TrialDetail,
)
from .schema import Landscape
from .subpop import extract_sub_population


def slugify(condition: str) -> str:
    """A stable landscape id for a condition (the events/links partition key)."""
    slug = re.sub(r"[^a-z0-9]+", "-", condition.lower()).strip("-")
    return slug or "landscape"


def _ctgov_events(search_pipeline: Callable[[str], list[dict]], condition: str) -> list[DevelopmentEvent]:
    events: list[DevelopmentEvent] = []
    for study in search_pipeline(condition):
        # Scope each trial's indication to the searched condition so the
        # landscape's indication list stays relevant (see _focus_condition).
        events.extend(study_to_events(study, focus_condition=condition))
    return events


def get_landscape(
    store,
    condition: str,
    as_of: str | None = None,
    search_pipeline: Callable[[str], list[dict]] | None = None,
    refresh: bool = False,
) -> Landscape:
    """Assemble the competitive matrix for a condition, as of a date.

    Seeds CT.gov-derived events into the store on first access (when a search
    function is supplied and nothing is stored yet), then assembles from the
    stored events + any ingested announcements + the evidence links.

    `refresh=True` drops the condition's cached CT.gov events first, forcing a
    re-pull from the live search — the way to clean a stale cache (e.g. one
    seeded before a search-scoping fix). Ingested announcements and evidence
    links are keyed separately and are preserved.
    """
    lid = slugify(condition)
    if refresh and search_pipeline is not None:
        store.clear_events(lid)
    events = store.load_events(lid)
    notes: list[str] = []
    if not events and search_pipeline is not None:
        try:
            fresh = _ctgov_events(search_pipeline, condition)
        except Exception:
            # Live ClinicalTrials.gov can be unreachable (e.g. it 403s requests
            # from datacenter IPs). Degrade to whatever is already stored rather
            # than failing the whole request.
            fresh = []
            notes.append(
                "Live ClinicalTrials.gov lookup was unavailable; showing stored events only."
            )
        if fresh:
            store.save_events(lid, fresh)
            events = store.load_events(lid)

    links = store.load_links(lid)
    resolver = make_evidence_resolver(store)
    landscape = assemble_landscape(
        events, as_of, links, evidence_for=resolver, condition=condition
    )
    landscape.notes.extend(notes)
    return landscape


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


def company_pipeline(
    store,
    sponsor: str,
    as_of: str | None = None,
    search: Callable[[str], list[dict]] | None = None,
    openfda=None,
    refresh: bool = False,
) -> CompanyPipeline:
    """One company's entire pipeline across every indication, as of a date.

    The cross-condition sibling of `get_landscape`: events are seeded from a
    lead-sponsor CT.gov search (not condition-scoped) and stored under a
    `sponsor:<slug>` partition, so the same asset can surface once per indication.
    Assembly reuses the deterministic `assemble_landscape` (phase roll-up, readout
    events, evidence badges via the global link map) unchanged; FDA approvals for
    the sponsor are attached from openFDA. Every remote source degrades to empty
    with a note rather than failing the request.
    """
    lid = f"sponsor:{slugify(sponsor)}"
    notes: list[str] = []
    if refresh and search is not None:
        store.clear_events(lid)
    events = store.load_events(lid)
    if not events and search is not None:
        try:
            fresh = [e for s in search(sponsor) for e in study_to_events(s)]
        except Exception:
            fresh = []
            notes.append(
                "Live ClinicalTrials.gov lookup was unavailable; showing stored events only."
            )
        if fresh:
            store.save_events(lid, fresh)
            events = store.load_events(lid)

    # Reuse the global (asset, indication) -> question_id link map so a company's
    # cells still carry any living-evidence badge that was linked on a condition
    # landscape — the same asset×indication key resolves either way.
    links = store.load_all_links()
    resolver = make_evidence_resolver(store)
    landscape = assemble_landscape(
        events, as_of, links, evidence_for=resolver, condition=sponsor
    )

    approvals = []
    if openfda is not None:
        try:
            approvals = openfda.approvals_by_sponsor(sponsor)
        except Exception:
            approvals = []
            notes.append("Live openFDA lookup was unavailable; approvals omitted.")

    return CompanyPipeline(
        sponsor=sponsor,
        as_of=as_of,
        assets=landscape.assets,
        indications=landscape.indications,
        cells=landscape.cells,
        approvals=approvals,
        notes=landscape.notes + notes,
    )


# --- v2: asset dossiers + indication mapping --------------------------------


def _dossier_evidence_resolver(store):
    """Resolve (asset, indication) -> evidence badge via the global links map."""
    links = store.load_all_links()
    badge_for = make_evidence_resolver(store)

    def resolve(asset: str, indication: str) -> EvidenceBadge | None:
        qid = links.get((asset, indication))
        return badge_for(qid) if qid else None

    return resolve


def _trials_with_subpop(store, studies, llm_client) -> list[TrialDetail]:
    """Build TrialDetails and attach each trial's sub-population (cached per NCT)."""
    ncts = [_nct(s) for s in studies]
    cached = store.load_subpops(ncts)
    trials: list[TrialDetail] = []
    for study in studies:
        nct = _nct(study)
        detail = study_to_trial_detail(study)
        sub = cached.get(nct)
        if sub is None:
            sub = extract_sub_population(study, llm_client=llm_client)
            store.save_subpop(nct, sub)  # cache (keyless -> base indication, still cached)
        detail.sub_population = sub
        trials.append(detail)
    return trials


def asset_dossier(
    store,
    asset: str,
    *,
    search=None,
    openfda=None,
    selection: SourceSelection | None = None,
    llm_client=None,
) -> AssetDossier:
    """Aggregate everything known about an asset: trials, geography, readouts,
    events, sub-indications, approvals, and the living evidence."""
    selection = selection or SourceSelection.default()
    notes: list[str] = []
    try:
        studies = search(asset) if search is not None else []
    except Exception:
        studies, _n = [], notes.append(
            "Live ClinicalTrials.gov lookup was unavailable."
        )

    trials = _trials_with_subpop(store, studies, llm_client)
    events = [e for s in studies for e in study_to_events(s)]

    approvals = []
    if selection.allows(Source.OPENFDA) and openfda is not None:
        approvals = store.load_approvals(asset)
        if not approvals:
            try:
                approvals = openfda.approvals_for(asset)
            except Exception:
                approvals = []
            if approvals:
                store.save_approvals(approvals)

    dossier = build_asset_dossier(
        asset,
        trials,
        events,
        selection=selection,
        approvals=approvals,
        evidence_for=_dossier_evidence_resolver(store),
    )
    dossier.notes.extend(notes)
    return dossier


def indication_map(
    store,
    indication: str,
    *,
    search=None,
    selection: SourceSelection | None = None,
    llm_client=None,
) -> IndicationMap:
    """Break an indication into its sub-populations, bottom-up from the trials."""
    selection = selection or SourceSelection.default()
    notes: list[str] = []
    try:
        studies = search(indication) if search is not None else []
    except Exception:
        studies = []
        notes.append("Live ClinicalTrials.gov lookup was unavailable.")

    trials = _trials_with_subpop(store, studies, llm_client)
    imap = build_indication_map(indication, trials, selection=selection)
    imap.notes.extend(notes)
    return imap
