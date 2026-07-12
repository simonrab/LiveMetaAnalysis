"""Trial search: turn a PICO into a query and return candidate trials.

Discovery spans two sources so the search is genuinely systematic, not a single
registry: ClinicalTrials.gov v2 (structured results, the primary source) and
Europe PMC (the published literature). The query builder is deterministic (no
LLM); Claude-driven query refinement is a later slice.

Deduplication here is at the *reference-id* level (an id appears once). True
cross-registry deduplication — matching a trial's ClinicalTrials.gov NCT to its
Europe PMC journal record — is deferred; because effect numbers are only pooled
from CT.gov's structured results (a Europe PMC-only record flags at extraction
rather than pooling), a trial surfaced by both sources cannot be double-counted
in the pooled estimate.
"""

from __future__ import annotations

from . import expand as expand_mod
from .schema import PICO, TrialCandidate
from .sources.clinicaltrials import ClinicalTrialsClient
from .sources.europepmc import EuropePmcClient


def build_query(pico: PICO) -> str:
    """A CT.gov free-text term from the intervention and outcome only.

    Population *and* comparator are deliberately left out: both over-constrain
    CT.gov's free-text AND-match. The comparator (usually "Placebo") drops every
    active-comparator trial and every record that just doesn't index the word,
    collapsing broad questions to one or two hits. Both fields are still used
    downstream for eligibility and extraction — they just don't narrow the
    candidate search here.
    """
    parts = [p.strip() for p in (pico.intervention, pico.outcome) if p and p.strip()]
    return " AND ".join(parts)


def search_trials(
    pico: PICO,
    max_results: int = 1000,
    client: ClinicalTrialsClient | None = None,
    epmc_client: EuropePmcClient | None = None,
    interventional_only: bool = True,
    llm_client=None,
) -> list[TrialCandidate]:
    """Search both sources for candidate trials matching the PICO.

    ClinicalTrials.gov leads (it's the primary, structured source and keeps the
    pool deterministic); Europe PMC records follow. The intervention is first
    *expanded* — a pharmacologic class ("GLP-1 receptor agonist") into its member
    agents (`expand`), because CT.gov indexes trials by specific drug, not class —
    and each agent is searched with `query.intr` and unioned. The outcome distils
    to a concise `query.term` that prunes without dropping trials.
    `interventional_only` (on by default) applies CT.gov's study-type filter at the
    API — the first, cheapest screen. Europe PMC being unavailable degrades
    discovery to CT.gov alone rather than failing the search.
    """
    ctgov_injected = client is not None
    client = client or ClinicalTrialsClient()
    query = build_query(pico)
    terms = expand_mod.search_terms(pico.intervention, llm_client=llm_client)
    outcome_term = expand_mod.outcome_keyword(pico.outcome, llm_client=llm_client)

    candidates: list[TrialCandidate] = []
    seen: set[str] = set()

    for term in terms:
        for h in client.search_agent_studies(
            term,
            term=outcome_term,
            page_size=max_results,
            interventional_only=interventional_only,
        ):
            nct = h.get("nct_id")
            if nct and nct not in seen:
                seen.add(nct)
                candidates.append(
                    TrialCandidate(nct_id=nct, title=h.get("title", ""))
                )

    # Europe PMC uses the injected client; else a live one is constructed only on
    # the fully default path. A caller that injects a specific CT.gov client (a
    # test, or `parse_question`) opts into Europe PMC by injecting one too, rather
    # than triggering unexpected live I/O.
    epmc = epmc_client
    if epmc is None and not ctgov_injected:
        epmc = EuropePmcClient()
    if epmc is not None:
        try:
            for h in epmc.search_studies(query, page_size=max_results):
                ref = h.get("id")
                if ref and ref not in seen:
                    seen.add(ref)
                    candidates.append(
                        TrialCandidate(
                            nct_id=ref, title=h.get("title", ""), source="europepmc"
                        )
                    )
        except Exception:
            # Discovery must never fail on a second-source outage — degrade to the
            # ClinicalTrials.gov candidates already collected.
            pass

    return candidates
