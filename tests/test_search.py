"""Trial search: PICO -> query -> candidates, mapped from CT.gov v2.

The HTTP layer is mocked with respx so the test runs offline.
"""

import httpx
import respx

from livemeta.core import search
from livemeta.core.schema import PICO, TrialCandidate

STUDIES_URL = "https://clinicaltrials.gov/api/v2/studies"


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
