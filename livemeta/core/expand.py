"""Expand a drug-*class* intervention into the member agents to search for.

CLAUDE.md division of labour: ClinicalTrials.gov indexes a trial by its specific
intervention (liraglutide, semaglutide, …), never by pharmacologic class, so a
class-level PICO ("GLP-1 receptor agonist") AND-matches almost nothing. A human
systematic reviewer expands the class into its agents and ORs them; this module
does the same, and Claude does the naming — it reads and structures, we do not
keep a baked-in list of drugs or keywords. With no model available the search
degrades honestly to the literal term rather than falling back to a hardcoded set.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_HINT = (
    "You expand a drug intervention for a ClinicalTrials.gov search. If the "
    "intervention names a pharmacologic CLASS (e.g. 'GLP-1 receptor agonist', "
    "'SGLT2 inhibitor'), set is_class=true and list the specific generic drug "
    "names (INN) that belong to that class — the ones a trials registry would "
    "index. If it is already a single specific drug, set is_class=false and leave "
    "agents empty. Never invent a drug you are not sure exists."
)


class _AgentList(BaseModel):
    is_class: bool = False
    agents: list[str] = Field(default_factory=list)


class _OutcomeKeyword(BaseModel):
    keyword: str = ""


_OUTCOME_HINT = (
    "You are building a ClinicalTrials.gov free-text filter for a review's outcome. "
    "Given the outcome, return a SHORT keyword phrase (1-3 words) that a registry "
    "would index the relevant trials under — e.g. '3-point MACE (CV death, non-fatal "
    "MI, non-fatal stroke)' -> 'cardiovascular outcomes'. Prefer recall: a broad "
    "clinical term over a literal acronym. Return an empty keyword if no useful "
    "narrowing term exists."
)


def _resolve_client(llm_client):
    if llm_client is not None:
        return llm_client
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - only with a real key
            import anthropic

            return anthropic.Anthropic()
        except Exception:
            return None
    return None


def expand_intervention(intervention: str, *, llm_client=None) -> list[str]:
    """Member agents to search for, or `[intervention]` when it is not a class.

    Claude expands a class into its agents when a model is available and confident.
    With no model — or if it judges the intervention a single drug — the term is
    searched as-is. There is no baked-in class list: an unavailable model degrades
    to the literal term rather than to a hardcoded set of drugs.
    """
    client = _resolve_client(llm_client)
    if client is not None:
        try:
            read: _AgentList = client.messages.parse(
                model=os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL),
                max_tokens=512,
                system=_SYSTEM_HINT,
                messages=[{"role": "user", "content": f"Intervention: {intervention}"}],
                output_format=_AgentList,
            ).parsed_output
            agents = [a.strip() for a in read.agents if a and a.strip()]
            if read.is_class and agents:
                return agents
        except Exception:
            pass
    return [intervention]


def outcome_keyword(outcome: str, *, llm_client=None) -> str | None:
    """A concise CT.gov `query.term` for the outcome, or None to skip narrowing.

    The outcome text ("3-point MACE (CV death, non-fatal MI, non-fatal stroke)")
    is far too literal to AND-match a registry, so Claude distils it to a broad
    indexed phrase ("cardiovascular outcomes") that prunes the per-agent candidate
    set without dropping trials. With no model we return None — a broader search
    keeps recall rather than falling back to a hardcoded keyword map.
    """
    client = _resolve_client(llm_client)
    if client is not None:
        try:
            read: _OutcomeKeyword = client.messages.parse(
                model=os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL),
                max_tokens=128,
                system=_OUTCOME_HINT,
                messages=[{"role": "user", "content": f"Outcome: {outcome}"}],
                output_format=_OutcomeKeyword,
            ).parsed_output
            keyword = read.keyword.strip()
            if keyword:
                return keyword
        except Exception:
            pass
    return None


def search_terms(intervention: str, *, llm_client=None) -> list[str]:
    """The CT.gov `query.intr` terms for one PICO intervention, de-duplicated.

    For a class, the member agents Claude named (each a specific drug the registry
    indexes); for a specific drug (or with no model), just that term. The *class*
    term is never searched as a standalone `query.intr` when agents exist: it
    free-text-matches every trial that merely mentions the class, swamping the set.
    """
    agents = expand_intervention(intervention, llm_client=llm_client)
    terms: list[str] = []
    seen: set[str] = set()
    for term in agents:
        key = term.strip().lower()
        if key and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms
