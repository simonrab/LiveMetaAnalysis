"""Drug-class -> member-agent expansion for systematic search.

CT.gov indexes interventions by specific drug name, not by pharmacologic class,
so a class-level PICO ("GLP-1 receptor agonist") recalls almost nothing. Expanding
the class into its member agents and searching per-agent is what a human reviewer
does. Claude names the agents; there is no baked-in drug or keyword list — with no
model the search degrades honestly to the literal term.
"""

from livemeta.core import expand


class _FakeParsed:
    def __init__(self, obj):
        self.parsed_output = obj


class _FakeMessages:
    def __init__(self, agents):
        self._agents = agents

    def parse(self, **kwargs):
        read = expand._AgentList(is_class=True, agents=self._agents)
        return _FakeParsed(read)


class _FakeClient:
    def __init__(self, agents):
        self.messages = _FakeMessages(agents)


def test_llm_expansion_is_used_when_a_client_is_present():
    client = _FakeClient(["drugA", "drugB", "drugC"])
    agents = expand.expand_intervention("GLP-1 receptor agonist", llm_client=client)
    assert agents == ["drugA", "drugB", "drugC"]


def test_class_without_a_model_degrades_to_the_literal_term():
    # No LLM and no baked-in class list: the class is searched as its own term
    # rather than expanded from a hardcoded table of drugs.
    assert expand.expand_intervention("GLP-1 receptor agonist", llm_client=None) == [
        "GLP-1 receptor agonist"
    ]


def test_specific_drug_returns_itself_without_a_model():
    assert expand.expand_intervention("liraglutide", llm_client=None) == ["liraglutide"]


def test_search_terms_are_the_agents_the_model_named_not_the_class():
    # When the model expands a class, only its member agents are searched as
    # query.intr — never the class term (which free-text-matches hundreds).
    client = _FakeClient(["liraglutide", "semaglutide", "dulaglutide"])
    terms = expand.search_terms("GLP-1 receptor agonist", llm_client=client)
    assert "GLP-1 receptor agonist" not in terms
    assert terms == ["liraglutide", "semaglutide", "dulaglutide"]


def test_search_terms_degrade_to_the_term_without_a_model():
    assert expand.search_terms("liraglutide", llm_client=None) == ["liraglutide"]


class _FakeKeywordMessages:
    def __init__(self, keyword):
        self._keyword = keyword

    def parse(self, **kwargs):
        return _FakeParsed(expand._OutcomeKeyword(keyword=self._keyword))


class _FakeKeywordClient:
    def __init__(self, keyword):
        self.messages = _FakeKeywordMessages(keyword)


def test_outcome_keyword_uses_claude_when_present():
    client = _FakeKeywordClient("cardiovascular outcomes")
    assert (
        expand.outcome_keyword("3-point MACE (CV death, non-fatal MI)", llm_client=client)
        == "cardiovascular outcomes"
    )


def test_outcome_keyword_is_none_without_a_model():
    # No model, no baked-in keyword map: no narrowing term (a broader search keeps
    # recall) rather than a fabricated keyword.
    assert expand.outcome_keyword("3-point MACE (CV death)", llm_client=None) is None
