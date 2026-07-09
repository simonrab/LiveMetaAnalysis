"""Trial search: turn a PICO into a query and return candidate trials.

Wraps the ClinicalTrials.gov v2 free-text search. The query builder is
deterministic (no LLM); Claude-driven query refinement is a later slice.
"""

from __future__ import annotations

from .schema import PICO, TrialCandidate
from .sources.clinicaltrials import ClinicalTrialsClient


def build_query(pico: PICO) -> str:
    """A CT.gov free-text term from the intervention, comparator, and outcome.

    Population is deliberately left out of the term: it over-constrains CT.gov's
    free-text match. Eligibility filtering happens downstream, not in the query.
    """
    parts = [p.strip() for p in (pico.intervention, pico.comparator, pico.outcome) if p and p.strip()]
    return " AND ".join(parts)


def search_trials(
    pico: PICO, max_results: int = 1000, client: ClinicalTrialsClient | None = None
) -> list[TrialCandidate]:
    """Search CT.gov for candidate trials matching the PICO."""
    client = client or ClinicalTrialsClient()
    query = build_query(pico)
    hits = client.search_studies(query, page_size=max_results)
    return [
        TrialCandidate(nct_id=h.get("nct_id", ""), title=h.get("title", ""))
        for h in hits
        if h.get("nct_id")
    ]
