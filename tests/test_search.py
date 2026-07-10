"""Trial search: PICO -> query -> candidates, mapped from CT.gov v2.

The HTTP layer is mocked with respx so the test runs offline.
"""

import httpx
import respx

from livemeta.core import search
from livemeta.core.schema import PICO, TrialCandidate

STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"
EPMC_SEARCH_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


def _pico() -> PICO:
    return PICO(
        population="adults with type 2 diabetes",
        intervention="GLP-1 receptor agonist",
        comparator="placebo",
        outcome="MACE",
    )


def test_build_query_includes_intervention_and_outcome():
    q = search.build_query(_pico())
    assert "GLP-1" in q
    assert "MACE" in q


def test_build_query_excludes_comparator_and_population():
    # Comparator ("placebo") and population over-constrain CT.gov's AND-match, so
    # they are left out of the search term (still used downstream).
    q = search.build_query(_pico()).lower()
    assert "placebo" not in q
    assert "diabetes" not in q  # population term absent
    assert "glp-1 receptor agonist" in q
    assert "mace" in q


@respx.mock
def test_search_trials_maps_hits_to_candidates():
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "studies": [
                    {
                        "protocolSection": {
                            "identificationModule": {
                                "nctId": "NCT01179048",
                                "briefTitle": "LEADER",
                            }
                        }
                    }
                ]
            },
        )
    )

    hits = search.search_trials(_pico(), max_results=5)

    assert route.called
    assert hits == [TrialCandidate(nct_id="NCT01179048", title="LEADER")]


@respx.mock
def test_search_trials_default_cap_is_1000():
    # The default candidate cap is CT.gov's per-request max, so broad questions
    # aren't silently truncated.
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(200, json={"studies": []})
    )

    search.search_trials(_pico())

    assert route.called
    assert route.calls.last.request.url.params["pageSize"] == "1000"


@respx.mock
def test_search_trials_filters_to_interventional_by_default():
    # First deterministic screen: narrow the candidate set to interventional
    # trials at the API so observational records never enter the pipeline.
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(200, json={"studies": []})
    )

    search.search_trials(_pico())

    assert route.called
    adv = route.calls.last.request.url.params["filter.advanced"]
    assert "StudyType" in adv and "INTERVENTIONAL" in adv


@respx.mock
def test_search_studies_omits_filter_when_not_interventional_only():
    route = respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(200, json={"studies": []})
    )

    from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

    ClinicalTrialsClient().search_studies("GLP-1 MACE")  # default: no design filter

    assert "filter.advanced" not in route.calls.last.request.url.params


# --- Multi-source discovery: CT.gov + Europe PMC ----------------------------


def _ctgov_hit(nct: str, title: str) -> dict:
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": title}
        }
    }


def _epmc_result(rid: str, pmid: str | None, pmcid: str | None, title: str) -> dict:
    r = {"id": pmid or pmcid or rid, "title": title}
    if pmid:
        r["pmid"] = pmid
    if pmcid:
        r["pmcid"] = pmcid
    return r


@respx.mock
def test_search_trials_merges_europe_pmc_records():
    # Discovery spans both sources: a systematic search is not a single registry.
    respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(
            200, json={"studies": [_ctgov_hit("NCT01179048", "LEADER")]}
        )
    )
    epmc = respx.get(EPMC_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "resultList": {
                    "result": [_epmc_result("x", "31234567", None, "A CV outcomes paper")]
                }
            },
        )
    )

    hits = search.search_trials(_pico(), max_results=5)

    assert epmc.called
    assert TrialCandidate(nct_id="NCT01179048", title="LEADER") in hits
    epmc_hit = next(h for h in hits if h.source == "europepmc")
    assert epmc_hit.nct_id == "PMID:31234567"
    assert epmc_hit.title == "A CV outcomes paper"


@respx.mock
def test_search_trials_lists_ctgov_before_europe_pmc():
    # CT.gov (structured results) is the primary source and leads the candidate
    # order, so the pool/forest plot stay deterministic.
    respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(
            200, json={"studies": [_ctgov_hit("NCT01", "Registry trial")]}
        )
    )
    respx.get(EPMC_SEARCH_URL).mock(
        return_value=httpx.Response(
            200,
            json={"resultList": {"result": [_epmc_result("x", "999", None, "Paper")]}},
        )
    )

    sources = [h.source for h in search.search_trials(_pico())]

    assert sources == ["clinicaltrials.gov", "europepmc"]


@respx.mock
def test_search_trials_dedupes_repeated_reference_ids():
    respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "studies": [_ctgov_hit("NCT01", "A"), _ctgov_hit("NCT01", "A again")]
            },
        )
    )
    respx.get(EPMC_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"resultList": {"result": []}})
    )

    hits = search.search_trials(_pico())

    assert [h.nct_id for h in hits] == ["NCT01"]


@respx.mock
def test_search_trials_degrades_to_ctgov_when_europe_pmc_fails():
    # Europe PMC being down must never fail the search — discovery degrades to
    # ClinicalTrials.gov alone rather than raising.
    respx.get(STUDIES_URL).mock(
        return_value=httpx.Response(
            200, json={"studies": [_ctgov_hit("NCT01179048", "LEADER")]}
        )
    )
    respx.get(EPMC_SEARCH_URL).mock(return_value=httpx.Response(503))

    hits = search.search_trials(_pico())

    assert hits == [TrialCandidate(nct_id="NCT01179048", title="LEADER")]
