"""Deterministic CT.gov → competitive-intelligence parsing.

No Claude here: sponsor/phase/status/dates/interventions come straight from the
structured CT.gov v2 record the tool already fetches. Every derived event carries
provenance back to the trial. Mirrors the "no silent back-calculation" contract.
"""

import httpx
import respx

from livemeta.core.ci import ctgov_pipeline as cp
from livemeta.core.ci.schema import EventType, Phase, SourceType
from livemeta.core.sources.clinicaltrials import ClinicalTrialsClient

BASE = "https://clinicaltrials.gov/api/v2"


def _study(
    nct="NCT01234567",
    title="A Trial of Semaglutide in Type 2 Diabetes",
    phases=("PHASE3",),
    status="COMPLETED",
    start="2015-03",
    primary_completion="2018-06",
    sponsor="Novo Nordisk",
    sponsor_class="INDUSTRY",
    conditions=("Type 2 Diabetes",),
    interventions=(("DRUG", "Semaglutide"), ("DRUG", "Placebo")),
):
    return {
        "protocolSection": {
            "identificationModule": {"nctId": nct, "briefTitle": title},
            "sponsorCollaboratorsModule": {
                "leadSponsor": {"name": sponsor, "class": sponsor_class}
            },
            "designModule": {"phases": list(phases)},
            "statusModule": {
                "overallStatus": status,
                "startDateStruct": {"date": start},
                "primaryCompletionDateStruct": {"date": primary_completion},
            },
            "conditionsModule": {"conditions": list(conditions)},
            "armsInterventionsModule": {
                "interventions": [{"type": t, "name": n} for t, n in interventions]
            },
        }
    }


# --- study_to_asset ---------------------------------------------------------


def test_asset_reads_drug_sponsor_and_class():
    asset = cp.study_to_asset(_study())
    assert asset.name == "Semaglutide"  # the non-placebo drug arm
    assert asset.sponsor == "Novo Nordisk"
    assert asset.sponsor_class == "INDUSTRY"
    assert asset.provenance and asset.provenance[0].trial_id == "NCT01234567"


def test_asset_skips_placebo_and_control_arms():
    study = _study(interventions=(("DRUG", "Placebo"), ("DRUG", "Tirzepatide")))
    assert cp.study_to_asset(study).name == "Tirzepatide"


# --- study_to_events --------------------------------------------------------


def test_events_emit_start_and_readout_with_phase_and_provenance():
    events = cp.study_to_events(_study())
    kinds = {e.event_type for e in events}
    assert EventType.TRIAL_START in kinds
    assert EventType.READOUT in kinds  # COMPLETED with a primary-completion date
    for e in events:
        assert e.phase == Phase.PHASE_3
        assert e.indication == "Type 2 Diabetes"
        assert e.source_type == SourceType.CTGOV
        assert e.provenance and e.provenance[0].trial_id == "NCT01234567"


def test_start_event_dated_and_normalized_to_iso():
    start = next(
        e for e in cp.study_to_events(_study()) if e.event_type == EventType.TRIAL_START
    )
    assert start.date == "2015-03-01"  # "YYYY-MM" padded to a sortable ISO date


def test_readout_only_when_completed_with_a_date():
    ongoing = _study(status="RECRUITING", primary_completion=None)
    kinds = {e.event_type for e in cp.study_to_events(ongoing)}
    assert EventType.READOUT not in kinds
    assert EventType.TRIAL_START in kinds


def test_phase_mapping_combined_phase_2_3():
    events = cp.study_to_events(_study(phases=("PHASE2", "PHASE3")))
    assert all(e.phase == Phase.PHASE_2_3 for e in events)


def test_missing_modules_do_not_crash():
    events = cp.study_to_events({"protocolSection": {"identificationModule": {"nctId": "NCT9"}}})
    # No dated milestones, but never raises; any event carries the trial id.
    for e in events:
        assert e.provenance[0].trial_id == "NCT9"


# --- search_pipeline (client) ----------------------------------------------


@respx.mock
def test_search_pipeline_requests_wide_fields_and_returns_raw_studies():
    payload = {"studies": [_study(nct="NCT1"), _study(nct="NCT2")]}
    route = respx.get(f"{BASE}/studies").mock(
        return_value=httpx.Response(200, json=payload)
    )
    studies = ClinicalTrialsClient().search_pipeline("semaglutide diabetes", page_size=2)

    assert [s["protocolSection"]["identificationModule"]["nctId"] for s in studies] == [
        "NCT1",
        "NCT2",
    ]
    fields = route.calls.last.request.url.params.get("fields")
    for module in (
        "sponsorCollaboratorsModule",
        "designModule",
        "statusModule",
        "armsInterventionsModule",
        "conditionsModule",
    ):
        assert module in fields
    ua = route.calls.last.request.headers.get("user-agent", "")
    assert "Mozilla" in ua  # reuses the browser UA; live backend 403s without it
