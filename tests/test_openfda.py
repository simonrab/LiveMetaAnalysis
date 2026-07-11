"""openFDA drugsfda client — parses approvals from a recorded-shape response."""

import httpx
import respx

from livemeta.core.sources.openfda import OpenFdaClient

BASE = "https://api.fda.gov/drug/drugsfda.json"

_PAYLOAD = {
    "results": [
        {
            "application_number": "NDA209637",
            "sponsor_name": "NOVO NORDISK INC",
            "openfda": {"brand_name": ["OZEMPIC"], "generic_name": ["SEMAGLUTIDE"]},
            "products": [{"brand_name": "OZEMPIC", "marketing_status": "Prescription"}],
            "submissions": [
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20171205"},
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20200116"},
            ],
        },
        {
            "application_number": "NDA213051",
            "sponsor_name": "NOVO NORDISK INC",
            "products": [{"brand_name": "RYBELSUS", "marketing_status": "Prescription"}],
            "submissions": [
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20190920"},
            ],
        },
    ]
}


@respx.mock
def test_parses_approvals_with_earliest_ap_date():
    respx.get(BASE).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    approvals = OpenFdaClient().approvals_for("semaglutide")
    assert [a.application_number for a in approvals] == ["NDA209637", "NDA213051"]
    ozempic = approvals[0]
    assert ozempic.sponsor == "NOVO NORDISK INC"
    assert ozempic.brand_names == ["OZEMPIC"]
    assert ozempic.approval_date == "2017-12-05"  # earliest AP submission
    assert ozempic.marketing_status == "Prescription"
    assert ozempic.indication_approx is None  # openFDA has no indication text
    assert ozempic.provenance[0].trial_id == "NDA209637"
    # Provenance points at the human-facing Drugs@FDA page, not the raw API JSON.
    assert ozempic.provenance[0].source_url == (
        "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
        "?event=overview.process&ApplNo=209637"
    )


@respx.mock
def test_404_returns_empty_not_error():
    respx.get(BASE).mock(return_value=httpx.Response(404, json={"error": {"code": "NOT_FOUND"}}))
    assert OpenFdaClient().approvals_for("nonexistent-drug") == []


@respx.mock
def test_network_error_degrades_to_empty():
    respx.get(BASE).mock(side_effect=httpx.ConnectError("boom"))
    assert OpenFdaClient().approvals_for("semaglutide") == []


# --- approvals_by_sponsor (company view) ------------------------------------


@respx.mock
def test_approvals_by_sponsor_queries_identity_tokens_and_derives_drug():
    route = respx.get(BASE).mock(return_value=httpx.Response(200, json=_PAYLOAD))
    approvals = OpenFdaClient().approvals_by_sponsor("Novo Nordisk A/S")

    # Searched on the identity tokens (legal form "A/S" dropped), not a quoted
    # phrase — openFDA's sponsor_name would otherwise miss "NOVO NORDISK INC".
    assert route.calls.last.request.url.params.get("search") == "novo nordisk"
    assert [a.application_number for a in approvals] == ["NDA209637", "NDA213051"]
    # With no drug supplied, the label comes from the record's generic name.
    assert approvals[0].drug == "Semaglutide"
    assert approvals[0].sponsor == "NOVO NORDISK INC"
    assert approvals[0].brand_names == ["OZEMPIC"]
    assert approvals[0].approval_date == "2017-12-05"
    # A record with no generic name still yields an approval (drug falls back).
    assert approvals[1].drug == "Rybelsus"  # openfda absent -> derived from brand


@respx.mock
def test_approvals_by_sponsor_rejects_near_miss_sponsors():
    # openFDA's OR-token match returns near-misses; the precision gate must drop
    # any record whose sponsor_name lacks the most distinctive token ("nordisk").
    payload = {
        "results": [
            _PAYLOAD["results"][0],  # NOVO NORDISK INC — kept
            {
                "application_number": "NDA999",
                "sponsor_name": "NOVO",  # a different company, token "novo" only
                "products": [{"brand_name": "SOMETHING", "marketing_status": "Rx"}],
                "submissions": [
                    {"submission_status": "AP", "submission_status_date": "20200101"}
                ],
            },
        ]
    }
    respx.get(BASE).mock(return_value=httpx.Response(200, json=payload))
    approvals = OpenFdaClient().approvals_by_sponsor("Novo Nordisk A/S")
    assert [a.application_number for a in approvals] == ["NDA209637"]  # NDA999 dropped


@respx.mock
def test_approvals_by_sponsor_404_and_network_error_degrade_to_empty():
    respx.get(BASE).mock(return_value=httpx.Response(404, json={"error": {}}))
    assert OpenFdaClient().approvals_by_sponsor("Nobody Pharma") == []
    respx.get(BASE).mock(side_effect=httpx.ConnectError("boom"))
    assert OpenFdaClient().approvals_by_sponsor("Novo Nordisk") == []
