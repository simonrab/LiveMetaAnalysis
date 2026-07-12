"""The locked demo question: GLP-1 receptor agonists and cardiovascular events.

A recent, well-established meta-analysis (Sattar et al., Lancet Diabetes
Endocrinol 2021) pools these 8 cardiovascular outcome trials to a MACE hazard
ratio of ~0.86 (0.80-0.93) — a result judges can sanity-check.
"""

from .schema import PICO, EffectMeasure, Question

# 3-point MACE cardiovascular outcome trials of GLP-1 receptor agonists.
GLP1_CVOT_TRIALS = [
    "NCT01147250",  # ELIXA (lixisenatide)
    "NCT01179048",  # LEADER (liraglutide)
    "NCT01720446",  # SUSTAIN-6 (semaglutide s.c.)
    "NCT01144338",  # EXSCEL (exenatide)
    "NCT02465515",  # HARMONY OUTCOMES (albiglutide)
    "NCT01394952",  # REWIND (dulaglutide)
    "NCT02692716",  # PIONEER-6 (oral semaglutide)
    "NCT03496298",  # AMPLITUDE-O (efpeglenatide)
]

GLP1_MACE_QUESTION = Question(
    id="glp1-mace",
    text=(
        "In adults with type 2 diabetes or high cardiovascular risk, do GLP-1 "
        "receptor agonists versus placebo reduce major adverse cardiovascular "
        "events (MACE)?"
    ),
    pico=PICO(
        population="Adults with type 2 diabetes or established cardiovascular risk",
        intervention="GLP-1 receptor agonist",
        comparator="Placebo",
        outcome="3-point MACE (CV death, non-fatal MI, non-fatal stroke)",
    ),
    measure=EffectMeasure.HR,
    trial_ids=GLP1_CVOT_TRIALS,
)

# AMPLITUDE-O (efpeglenatide, 2021) — a recent GLP-1 cardiovascular readout,
# referenced by the living-update tests as the trial to inject.
HELD_OUT_TRIAL = "NCT03496298"  # AMPLITUDE-O

# The product-facing demo question: the *same* PICO but with no trial_ids, so a
# live run discovers its trials through the real systematic search (Claude expands
# the GLP-1 class into agents, queries CT.gov, screens) rather than replaying a
# curated list. GLP1_CVOT_TRIALS remains only as the offline test-fixture set.
GLP1_MACE_DISCOVER = GLP1_MACE_QUESTION.model_copy(update={"trial_ids": []})


def discover_demo_trials(pico, *, search_client=None, llm_client=None) -> list[str]:
    """NCT ids for the demo PICO from a genuine ClinicalTrials.gov search.

    Runs the systematic search (Claude expands the class into agents, each queried
    on CT.gov). Whatever the search returns is what the demo pools — no curated
    fallback list. If the search finds nothing the pipeline abstains honestly.
    """
    from .search import search_trials

    return [c.nct_id for c in search_trials(pico, client=search_client, llm_client=llm_client)]
