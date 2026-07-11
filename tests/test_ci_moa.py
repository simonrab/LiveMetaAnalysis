"""MoA clusters: inferred mechanism, INN-stem fallback, class-level evidence."""

import math

from livemeta.core.ci import moa
from livemeta.core.ci.schema import EvidenceBadge
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


def test_inn_stem_fallback_classifies_known_suffixes():
    assert moa._stem_class("Semaglutide") == "GLP-1 receptor agonists"
    assert moa._stem_class("Empagliflozin") == "SGLT2 inhibitors"
    assert moa._stem_class("Pembrolizumab") == "Monoclonal antibodies"
    assert moa._stem_class("Wonderdrugium") == moa.UNCLASSIFIED


def test_infer_uses_confident_llm_over_stem():
    class _Stub:
        class messages:
            @staticmethod
            def parse(**kwargs):
                class R:
                    parsed_output = moa._MoaRead(
                        found=True, confidence="high", drug_class="GLP-1/GIP dual agonist"
                    )

                return R()

    assert moa.infer_drug_class("Tirzepatide", [], llm_client=_Stub()) == "GLP-1/GIP dual agonist"


def test_low_confidence_llm_falls_back_to_stem():
    class _Stub:
        class messages:
            @staticmethod
            def parse(**kwargs):
                class R:
                    parsed_output = moa._MoaRead(found=True, confidence="low", drug_class="???")

                return R()

    # Falls back to the INN stem rather than trusting a low-confidence guess.
    assert moa.infer_drug_class("Semaglutide", [], llm_client=_Stub()) == "GLP-1 receptor agonists"


def test_moa_landscape_clusters_by_class_and_caches(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    studies = [
        _study(nct="NCT1", conditions=("Obesity",), phases=("PHASE3",),
               interventions=(("DRUG", "Semaglutide"),)),
        _study(nct="NCT2", conditions=("Obesity",), phases=("PHASE2",),
               interventions=(("DRUG", "Dulaglutide"),)),
        _study(nct="NCT3", conditions=("Obesity",), phases=("PHASE1",),
               interventions=(("DRUG", "Mysterymol"),)),
    ]
    result = moa.moa_landscape(store, "Obesity", search=lambda c: studies)

    by_class = {c.drug_class: c for c in result.clusters}
    glp1 = by_class["GLP-1 receptor agonists"]
    assert set(glp1.assets) == {"Semaglutide", "Dulaglutide"}
    assert glp1.program_count == 2
    # Unclassified always sinks to the bottom.
    assert result.clusters[-1].drug_class == moa.UNCLASSIFIED

    # The class was cached — no re-inference needed on a second pass.
    assert store.load_moa(["Semaglutide"]) == {"Semaglutide": "GLP-1 receptor agonists"}


def test_moa_attaches_class_level_evidence(tmp_path):
    store = SnapshotStore(data_dir=tmp_path)
    from livemeta.core.ci import service

    q = Question(
        id="glp1-mace", text="q",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
        measure=EffectMeasure.HR,
    )
    pool = PoolResult(
        measure=EffectMeasure.HR, engine="python", k=6,
        estimate=0.83, ci_low=0.76, ci_high=0.91, ci_method=CIMethod.WALD,
        estimate_log=math.log(0.83), se_log=0.04, ci_low_log=-0.27, ci_high_log=-0.09,
        tau2=0.0, i2=10.0, q=1.0, q_p=0.9,
    )
    store.save_snapshot(ReviewResult(question=q, pool=pool))

    studies = [_study(nct="NCT1", conditions=("Obesity",), phases=("PHASE3",),
                      interventions=(("DRUG", "Semaglutide"),))]
    service.get_landscape(store, "Obesity", search_pipeline=lambda c: studies)
    service.link_review(store, "Obesity", "Semaglutide", "Obesity", "glp1-mace")

    result = moa.moa_landscape(store, "Obesity", search=lambda c: studies)
    glp1 = next(c for c in result.clusters if c.drug_class == "GLP-1 receptor agonists")
    assert glp1.evidence is not None and glp1.evidence.state == "pooled"
    assert glp1.plain_summary == "benefit proven"
