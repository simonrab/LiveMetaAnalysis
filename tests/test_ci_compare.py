"""Side-by-side compare: operational facts line up; efficacy abstains.

The load-bearing assertions are the safety ones — the comparability gate defaults
to "not directly comparable", and each asset's evidence stays in its own context.
"""

import math

from livemeta.core.ci import compare
from livemeta.core.ci.schema import AssetEvidenceContext, EvidenceBadge
from livemeta.core.schema import (
    CIMethod,
    EffectMeasure,
    PICO,
    PoolResult,
    Question,
    ReviewResult,
)
from livemeta.core.store import SnapshotStore
from tests.test_ci_ctgov import _study


def _study_full(nct, asset, indication="Obesity", phase="PHASE3", enrollment=None,
                countries=(), pcd=None, has_results=False):
    s = _study(nct=nct, conditions=(indication,), phases=(phase,), status="RECRUITING",
               primary_completion=pcd, interventions=((("DRUG", asset)),))
    if enrollment is not None:
        s["protocolSection"]["designModule"]["enrollmentInfo"] = {"count": enrollment}
    if countries:
        s["protocolSection"]["contactsLocationsModule"] = {
            "locations": [{"country": c} for c in countries]
        }
    if has_results:
        s["protocolSection"]["statusModule"]["resultsFirstPostDateStruct"] = {"date": "2025-01"}
    return s


def _save_linked_review(store, qid, condition, asset, indication):
    from livemeta.core.ci import service

    q = Question(
        id=qid, text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=EffectMeasure.HR,
    )
    pool = PoolResult(
        measure=EffectMeasure.HR, engine="python", k=4,
        estimate=0.81, ci_low=0.74, ci_high=0.89, ci_method=CIMethod.WALD,
        estimate_log=math.log(0.81), se_log=0.04, ci_low_log=-0.30, ci_high_log=-0.12,
        tau2=0.0, i2=10.0, q=1.0, q_p=0.9,
    )
    store.save_snapshot(ReviewResult(question=q, pool=pool))
    service.link_review(store, condition, asset, indication, qid)


def _ctx(measure="HR", state="pooled", population="obesity", comparator=None):
    badge = EvidenceBadge(question_id="q", measure=measure, state=state,
                          estimate=0.8, ci_low=0.7, ci_high=0.9)
    return AssetEvidenceContext(asset_name="x", population=population,
                               comparator=comparator, badge=badge)


# --- the comparability gate (the safety core) -------------------------------


def test_unanchored_comparison_is_not_directly_comparable():
    # Same measure, same population, both pooled — but no common comparator.
    verdict = compare.assess_comparability(_ctx(), _ctx())
    assert verdict.directly_comparable is False
    assert any("comparator" in r for r in verdict.reasons)


def test_different_measures_are_flagged_incomparable():
    verdict = compare.assess_comparability(_ctx(measure="HR"), _ctx(measure="MD"))
    assert verdict.directly_comparable is False
    assert any("outcome measures" in r for r in verdict.reasons)


def test_anchored_identical_context_is_comparable():
    a = _ctx(comparator="placebo")
    b = _ctx(comparator="placebo")
    assert compare.assess_comparability(a, b).directly_comparable is True


# --- end-to-end -------------------------------------------------------------


def test_compare_lines_up_operational_facts_and_abstains_on_efficacy(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    catalog = {
        "DrugA": [_study_full("NCT1", "DrugA", enrollment=12500,
                              countries=("US", "UK", "DE"), pcd="2026-11")],
        "DrugB": [_study_full("NCT2", "DrugB", enrollment=17600,
                              countries=("US", "UK", "DE", "FR", "JP"), pcd=None)],
    }
    _save_linked_review(store, "a-mace", "Obesity", "DrugA", "Obesity")

    result = compare.compare_assets(
        store, ["DrugA", "DrugB"], indication="Obesity",
        search=lambda asset: catalog.get(asset, []), as_of="2026-01-01",
    )

    rows = {r.label: r for r in result.rows}
    assert rows["Enrollment"].values == ["12,500", "17,600"]
    assert rows["Enrollment"].more == [False, True]  # neutral marker on the larger
    assert rows["Geography"].more == [False, True]
    assert rows["Next readout"].values == ["2026-11-01", "—"]

    # Efficacy is NOT a comparison row.
    assert "Estimate" not in rows and "HR" not in rows

    # Each asset's evidence stands in its own context; the gate abstains.
    assert [e.asset_name for e in result.evidence] == ["DrugA", "DrugB"]
    drug_a = next(e for e in result.evidence if e.asset_name == "DrugA")
    assert drug_a.plain_summary == "benefit proven"
    assert result.comparability.directly_comparable is False
    assert result.comparability.reasons
