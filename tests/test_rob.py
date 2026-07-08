"""Risk of Bias (RoB 2): Claude reads and judges, code rolls up, human confirms.

These tests run offline with a stub LLM — the model is never hit. They pin the
two load-bearing deterministic behaviours: the overall roll-up from the five
domains, and the honest PENDING state when no key/model is available (we abstain,
never fabricate a judgment).
"""

from livemeta.core import rob
from livemeta.core.schema import RobDecision, RobDomain, RobJudgment


class _StubParsed:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _StubLLM:
    def __init__(self, parsed=None, raises=False):
        self._parsed = parsed
        self._raises = raises

    class _Messages:
        def __init__(self, outer):
            self._outer = outer

        def parse(self, **kwargs):
            if self._outer._raises:
                raise RuntimeError("model unavailable")
            return _StubParsed(self._outer._parsed)

    @property
    def messages(self):
        return _StubLLM._Messages(self)


STUDY = {
    "protocolSection": {
        "identificationModule": {"nctId": "NCT01000001", "briefTitle": "TRIAL-X"}
    }
}


def _domains(judgments):
    """Build the parse-model domains Claude would return, one judgment each."""
    return rob._RobDomains(
        domains=[
            rob._RobDomainOut(
                key=k, name=n, judgment=j, rationale="because", quote="a source quote"
            )
            for (k, n), j in zip(rob.ROB_DOMAINS, judgments)
        ]
    )


def test_overall_is_low_when_all_domains_low():
    parsed = _domains(["low"] * 5)
    a = rob.assess_rob(STUDY, llm_client=_StubLLM(parsed=parsed))
    assert a.study_id == "NCT01000001"
    assert a.label == "TRIAL-X"
    assert len(a.domains) == 5
    assert a.overall == RobJudgment.LOW
    # Every domain carries the source quote it rests on.
    assert all(d.source_quote and d.source_quote.snippet for d in a.domains)


def test_overall_is_some_concerns_when_a_domain_has_some_concerns():
    parsed = _domains(["low", "some_concerns", "low", "low", "low"])
    a = rob.assess_rob(STUDY, llm_client=_StubLLM(parsed=parsed))
    assert a.overall == RobJudgment.SOME_CONCERNS


def test_overall_is_high_when_any_domain_is_high():
    parsed = _domains(["low", "some_concerns", "low", "low", "high"])
    a = rob.assess_rob(STUDY, llm_client=_StubLLM(parsed=parsed))
    assert a.overall == RobJudgment.HIGH


def test_no_client_yields_pending_never_fabricated():
    a = rob.assess_rob(STUDY, llm_client=None)
    assert a.overall == RobJudgment.PENDING
    assert len(a.domains) == 5
    assert all(d.judgment == RobJudgment.PENDING for d in a.domains)
    assert all(d.source_quote is None for d in a.domains)


def test_model_failure_degrades_to_pending_without_raising():
    a = rob.assess_rob(STUDY, llm_client=_StubLLM(raises=True))
    assert a.overall == RobJudgment.PENDING


def test_apply_decisions_confirms_domains_and_rolls_up():
    parsed = _domains(["low"] * 5)
    a = rob.assess_rob(STUDY, llm_client=_StubLLM(parsed=parsed))

    # Confirm four of five domains — assessment is not yet fully signed off.
    partial = [
        RobDecision(study_id=a.study_id, domain_key=k)
        for (k, _n) in rob.ROB_DOMAINS[:4]
    ]
    a2 = rob.apply_rob_decisions(a, partial)
    assert sum(d.confirmed for d in a2.domains) == 4
    assert a2.confirmed is False

    # Confirm the last one — now the whole assessment is confirmed.
    full = partial + [RobDecision(study_id=a.study_id, domain_key=rob.ROB_DOMAINS[4][0])]
    a3 = rob.apply_rob_decisions(a, full)
    assert a3.confirmed is True
