"""Landscape service: seeding, ingest, linking, and the evidence join together.

Uses a real SQLite store, a fake CT.gov search (canned studies), and a stub LLM
client — no network, no key.
"""

from livemeta.core.ci import service
from livemeta.core.ci.schema import Phase
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    PICO,
    PoolResult,
    Question,
    ReviewResult,
)
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study  # reuse the CT.gov fixture builder
from tests.test_ci_ingest import _StubClient, _ext


def _search(studies):
    return lambda condition: studies


def test_slugify_is_stable_and_url_safe():
    assert service.slugify("Type 2 Diabetes") == "type-2-diabetes"
    assert service.slugify("!!!") == "landscape"


def test_get_landscape_seeds_ctgov_and_caches(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    calls = {"n": 0}

    def search(condition):
        calls["n"] += 1
        return [_study(nct="NCT1", interventions=(("DRUG", "Semaglutide"),))]

    ls = service.get_landscape(store, "Type 2 Diabetes", search_pipeline=search)
    assert "Semaglutide" in ls.assets
    assert calls["n"] == 1
    # Second call is served from the store — no re-fetch.
    service.get_landscape(store, "Type 2 Diabetes", search_pipeline=search)
    assert calls["n"] == 1


def test_refresh_clears_stale_cache_and_reseeds(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    # First seed carries a stale/off-target asset (the pre-fix query.term era).
    stale = _search([_study(nct="NCT1", interventions=(("DRUG", "Karolinska Cocktail"),))])
    ls = service.get_landscape(store, "Obesity", search_pipeline=stale)
    assert "Karolinska Cocktail" in ls.assets

    # A refresh drops the cache and re-pulls from the (now clean) search.
    fresh = _search([_study(nct="NCT2", interventions=(("DRUG", "Semaglutide"),))])
    refreshed = service.get_landscape(
        store, "Obesity", search_pipeline=fresh, refresh=True
    )
    assert "Semaglutide" in refreshed.assets
    assert "Karolinska Cocktail" not in refreshed.assets


def test_landscape_indications_are_scoped_to_the_condition_area(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        # Obesity trial that lists a comorbidity first.
        _study(nct="NCT1", conditions=("Hypertension", "Obesity"),
               interventions=(("DRUG", "DrugA"),)),
        _study(nct="NCT2", conditions=("Childhood Obesity",),
               interventions=(("DRUG", "DrugB"),)),
        # Obesity is only incidental (a cancer trial CT.gov linked to obesity).
        _study(nct="NCT3", conditions=("Breast Cancer",),
               interventions=(("DRUG", "DrugC"),)),
    ]
    ls = service.get_landscape(store, "Obesity", search_pipeline=_search(studies))
    # The dropdown shows only obesity-area indications — no comorbidity, no
    # off-target disease leaks in.
    assert "Hypertension" not in ls.indications
    assert "Breast Cancer" not in ls.indications
    assert set(ls.indications) == {"Obesity", "Childhood Obesity"}


def test_as_of_reconstructs_earlier_pipeline(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    study = _study(
        nct="NCT1",
        phases=("PHASE3",),
        start="2015-03",
        interventions=(("DRUG", "Semaglutide"),),
    )
    service.get_landscape(store, "T2D", search_pipeline=_search([study]))
    # Before the 2015 start there is nothing yet.
    early = service.get_landscape(store, "T2D", as_of="2014-01-01")
    assert early.cells == []


def test_ingest_adds_announcement_events_to_the_matrix(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    service.get_landscape(
        store, "T2D", search_pipeline=_search([_study(interventions=(("DRUG", "Semaglutide"),))])
    )
    client = _StubClient(
        [_ext(asset_name="Tirzepatide", indication="Type 2 Diabetes", phase="Phase 3")]
    )
    added = service.ingest_to_landscape(
        store, "T2D", "Lilly announces...", "PR:lilly", llm_client=client
    )
    assert len(added) == 1
    ls = service.get_landscape(store, "T2D")
    assert "Tirzepatide" in ls.assets


def test_link_surfaces_evidence_badge(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    # A saved review to link to.
    import math

    q = Question(
        id="glp1-mace",
        text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=EffectMeasure.HR,
    )
    pool = PoolResult(
        measure=EffectMeasure.HR, engine="python", k=6,
        estimate=0.86, ci_low=0.79, ci_high=0.93, ci_method=CIMethod.WALD,
        estimate_log=math.log(0.86), se_log=0.04, ci_low_log=-0.23, ci_high_log=-0.07,
        tau2=0.0, i2=10.0, q=1.0, q_p=0.9,
    )
    store.save_snapshot(ReviewResult(question=q, pool=pool))

    study = _study(
        nct="NCT1", conditions=("Type 2 Diabetes",), interventions=(("DRUG", "Semaglutide"),)
    )
    service.get_landscape(store, "Type 2 Diabetes", search_pipeline=_search([study]))
    service.link_review(store, "Type 2 Diabetes", "Semaglutide", "Type 2 Diabetes", "glp1-mace")

    ls = service.get_landscape(store, "Type 2 Diabetes")
    cell = next(c for c in ls.cells if c.asset_name == "Semaglutide")
    assert cell.question_id == "glp1-mace"
    assert cell.evidence is not None
    assert cell.evidence.state == "pooled"
    assert cell.evidence.conclusion == "significant reduction"


def test_live_search_failure_degrades_gracefully(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)

    def boom(condition):
        raise RuntimeError("403 Forbidden from CT.gov")

    ls = service.get_landscape(store, "T2D", search_pipeline=boom)
    assert ls.cells == []  # no crash
    assert any("unavailable" in n for n in ls.notes)


def test_asset_timeline_filters_by_name(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", interventions=(("DRUG", "Semaglutide"),)),
        _study(nct="NCT2", interventions=(("DRUG", "Tirzepatide"),)),
    ]
    service.get_landscape(store, "T2D", search_pipeline=_search(studies))
    timeline = service.asset_timeline(store, "T2D", "Semaglutide")
    assert timeline and all(e.asset_name == "Semaglutide" for e in timeline)


# --- company pipeline (cross-condition) -------------------------------------


class _FakeOpenFda:
    def __init__(self, approvals):
        self._approvals = approvals

    def approvals_by_sponsor(self, sponsor, limit=50):
        return list(self._approvals)


def _approval(drug, app_no="NDA1"):
    from livemeta.core.ci.schema import RegulatoryApproval

    return RegulatoryApproval(drug=drug, sponsor="Novo Nordisk", application_number=app_no)


def test_company_pipeline_spans_indications_and_keeps_real_conditions(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    # One sponsor, one asset, but two different indications — the whole point of
    # the cross-condition view is that both show, with their real condition names.
    studies = [
        _study(nct="NCT1", conditions=("Type 2 Diabetes",), phases=("PHASE3",),
               interventions=(("DRUG", "Semaglutide"),)),
        _study(nct="NCT2", conditions=("Obesity",), phases=("PHASE2",),
               interventions=(("DRUG", "Semaglutide"),)),
        _study(nct="NCT3", conditions=("Heart Failure",), phases=("PHASE1",),
               interventions=(("DRUG", "Ziltivekimab"),)),
    ]
    cp = service.company_pipeline(
        store, "Novo Nordisk", search=_search(studies),
        openfda=_FakeOpenFda([_approval("Semaglutide")]),
    )
    assert cp.sponsor == "Novo Nordisk"
    assert set(cp.indications) == {"Type 2 Diabetes", "Obesity", "Heart Failure"}
    assert set(cp.assets) == {"Semaglutide", "Ziltivekimab"}
    # The same asset appears once per indication (a cell each), at that trial's phase.
    sema = {(c.indication, c.current_phase) for c in cp.cells if c.asset_name == "Semaglutide"}
    assert (Phase.PHASE_3 in {p for _, p in sema}) and (Phase.PHASE_2 in {p for _, p in sema})
    assert [a.drug for a in cp.approvals] == ["Semaglutide"]


def test_company_pipeline_caches_and_as_of_filters(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    calls = {"n": 0}

    def search(sponsor):
        calls["n"] += 1
        return [_study(nct="NCT1", start="2015-03", phases=("PHASE3",),
                       interventions=(("DRUG", "Semaglutide"),))]

    service.company_pipeline(store, "Novo Nordisk", search=search)
    service.company_pipeline(store, "Novo Nordisk", search=search)
    assert calls["n"] == 1  # second call served from the store's sponsor partition
    early = service.company_pipeline(store, "Novo Nordisk", as_of="2014-01-01")
    assert early.cells == []  # before the 2015 start, nothing had happened


def test_company_pipeline_degrades_when_sources_unavailable(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)

    def boom(sponsor):
        raise RuntimeError("403 Forbidden from CT.gov")

    class _BoomFda:
        def approvals_by_sponsor(self, sponsor, limit=50):
            raise RuntimeError("openFDA down")

    cp = service.company_pipeline(store, "Novo Nordisk", search=boom, openfda=_BoomFda())
    assert cp.cells == [] and cp.approvals == []  # no crash
    assert any("unavailable" in n for n in cp.notes)
