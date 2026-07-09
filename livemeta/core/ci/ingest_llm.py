"""Claude reads a corporate announcement / filing into development events.

The competitive-intelligence sibling of `extract_text.py`: the model reports
what the document states (each event with the exact snippet and a self-reported
confidence), and deterministic code maps it to `DevelopmentEvent`s, dropping
anything not-found or low-confidence. The model never asserts a stage the text
does not state; with no key configured, ingest returns nothing rather than
inventing a pipeline.
"""

from __future__ import annotations

import os

from pydantic import BaseModel, Field

from ..schema import Provenance
from .schema import (
    DevelopmentEvent,
    EventType,
    ExtractedDevelopmentEvent,
    Phase,
    SourceType,
)

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_HINT = (
    "You are reading a corporate announcement, press release, or regulatory "
    "filing to log drug-development events for a competitive-intelligence "
    "landscape. For each drug-development milestone the document clearly states, "
    "return one event: the asset (drug) name, sponsor, indication, line of "
    "therapy if stated, the development phase (preclinical, phase 1, phase 1/2, "
    "phase 2, phase 2/3, phase 3, phase 4, filed, approved, or withdrawn), the "
    "event type, and the date if stated. Quote the exact sentence you read it "
    "from in source_snippet. Do NOT infer a stage the text does not state; if a "
    "milestone is unclear, set confidence to 'low'. Abstaining is correct, "
    "guessing is not."
)


class _ExtractedEvents(BaseModel):
    """The list of milestones Claude finds in one document."""

    events: list[ExtractedDevelopmentEvent] = Field(default_factory=list)


# Free-text phase label → our ordered Phase. Matched by normalized substring, so
# order matters: combined and higher roman numerals are checked first because
# "phase iii" contains "phase ii" which contains "phase i".
_PHASE_LOOKUP: list[tuple[tuple[str, ...], Phase]] = [
    (("preclinical",), Phase.PRECLINICAL),
    (("phase 1/2", "phase 1 / 2", "phase i/ii"), Phase.PHASE_1_2),
    (("phase 2/3", "phase 2 / 3", "phase ii/iii"), Phase.PHASE_2_3),
    (("phase 4", "phase iv"), Phase.PHASE_4),
    (("phase 3", "phase iii"), Phase.PHASE_3),
    (("phase 2", "phase ii"), Phase.PHASE_2),
    (("phase 1", "phase i"), Phase.PHASE_1),
    (("filed", "submitted", "nda", "bla", "marketing authorization application"), Phase.FILED),
    (("approved", "approval"), Phase.APPROVED),
    (("withdrawn", "discontinued", "terminated"), Phase.WITHDRAWN),
]

_EVENT_TYPE_LOOKUP: list[tuple[tuple[str, ...], EventType]] = [
    (("approval", "approved"), EventType.APPROVAL),
    (("filing", "filed", "submitted"), EventType.FILING),
    (("readout", "results", "data", "topline", "top-line", "met "), EventType.READOUT),
    (("initiat", "start", "dosed", "enrol"), EventType.TRIAL_START),
]


def _map_phase(raw: str) -> Phase:
    text = (raw or "").lower().replace("-", " ")
    for needles, phase in _PHASE_LOOKUP:
        if any(n in text for n in needles):
            return phase
    return Phase.UNKNOWN


def _map_event_type(raw: str) -> EventType:
    text = (raw or "").lower()
    for needles, etype in _EVENT_TYPE_LOOKUP:
        if any(n in text for n in needles):
            return etype
    return EventType.ANNOUNCEMENT


def _resolve_client(llm_client):
    if llm_client is not None:
        return llm_client
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:  # pragma: no cover - exercised only with a real key
            import anthropic

            return anthropic.Anthropic()
        except Exception:
            return None
    return None


def _to_event(parsed: ExtractedDevelopmentEvent, source_label: str) -> DevelopmentEvent:
    return DevelopmentEvent(
        asset_name=parsed.asset_name,
        indication=parsed.indication or "Unspecified",
        line_of_therapy=parsed.line_of_therapy,
        phase=_map_phase(parsed.phase),
        status=None,
        event_type=_map_event_type(parsed.event_type),
        date=parsed.date,
        source_type=SourceType.ANNOUNCEMENT,
        sponsor=parsed.sponsor,
        provenance=[
            Provenance(
                trial_id=source_label,
                snippet=parsed.source_snippet,
                field="announcement",
            )
        ],
    )


def ingest_announcement(
    text: str, source_label: str, llm_client=None
) -> list[DevelopmentEvent]:
    """Structure a free-text announcement/filing into development events.

    Only high/moderate-confidence, found milestones with an asset name become
    events; the rest are dropped (the tool abstains rather than inventing a
    stage). With no model available, returns an empty list.
    """
    client = _resolve_client(llm_client)
    if client is None:
        return []

    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
        parsed: _ExtractedEvents = client.messages.parse(
            model=model,
            max_tokens=1500,
            system=_SYSTEM_HINT,
            messages=[{"role": "user", "content": text}],
            output_format=_ExtractedEvents,
        ).parsed_output
    except Exception:
        return []

    events: list[DevelopmentEvent] = []
    for e in parsed.events:
        if not e.found or e.confidence == "low" or not e.asset_name.strip():
            continue
        events.append(_to_event(e, source_label))
    return events
