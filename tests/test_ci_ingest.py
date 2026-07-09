"""Free-text ingest: Claude reads an announcement, code decides what to keep.

Mirrors the extract_text discipline — provenance required, low-confidence and
not-found dropped, keyless returns nothing (never fabricates a pipeline).
"""

from livemeta.core.ci import ingest_llm
from livemeta.core.ci.ingest_llm import ingest_announcement
from livemeta.core.ci.schema import EventType, Phase, SourceType


class _StubParsed:
    def __init__(self, output):
        self.parsed_output = output


class _StubMessages:
    def __init__(self, output):
        self._output = output

    def parse(self, **kwargs):
        return _StubParsed(self._output)


class _StubClient:
    """Returns a canned _ExtractedEvents, ignoring the prompt."""

    def __init__(self, events):
        payload = ingest_llm._ExtractedEvents(events=events)
        self.messages = _StubMessages(payload)


def _ext(**kw):
    from livemeta.core.ci.schema import ExtractedDevelopmentEvent

    base = dict(found=True, confidence="high", source_snippet="quote")
    base.update(kw)
    return ExtractedDevelopmentEvent(**base)


def test_high_confidence_event_becomes_development_event():
    client = _StubClient(
        [
            _ext(
                asset_name="Tirzepatide",
                sponsor="Eli Lilly",
                indication="Obesity",
                phase="Phase 3",
                event_type="topline results",
                date="2023-07-01",
            )
        ]
    )
    events = ingest_announcement("...", "PR:lilly-2023", llm_client=client)
    assert len(events) == 1
    e = events[0]
    assert e.asset_name == "Tirzepatide"
    assert e.phase == Phase.PHASE_3
    assert e.event_type == EventType.READOUT
    assert e.source_type == SourceType.ANNOUNCEMENT
    assert e.provenance[0].trial_id == "PR:lilly-2023"
    assert e.provenance[0].snippet == "quote"


def test_low_confidence_and_not_found_are_dropped():
    client = _StubClient(
        [
            _ext(asset_name="DrugX", phase="Phase 2", confidence="low"),
            _ext(asset_name="DrugY", phase="Phase 3", found=False),
            _ext(asset_name="", phase="Phase 3"),  # no asset name
        ]
    )
    assert ingest_announcement("...", "PR:x", llm_client=client) == []


def test_multiple_events_in_one_document():
    client = _StubClient(
        [
            _ext(asset_name="DrugA", phase="approved", event_type="FDA approval"),
            _ext(asset_name="DrugB", phase="Phase III", event_type="trial initiation"),
        ]
    )
    events = ingest_announcement("...", "PR:multi", llm_client=client)
    assert {e.asset_name for e in events} == {"DrugA", "DrugB"}
    by_asset = {e.asset_name: e for e in events}
    assert by_asset["DrugA"].phase == Phase.APPROVED
    assert by_asset["DrugA"].event_type == EventType.APPROVAL
    assert by_asset["DrugB"].phase == Phase.PHASE_3


def test_phase_label_variants_map():
    assert ingest_llm._map_phase("Phase III") == Phase.PHASE_3
    assert ingest_llm._map_phase("phase 1/2 study") == Phase.PHASE_1_2
    assert ingest_llm._map_phase("received FDA approval") == Phase.APPROVED
    assert ingest_llm._map_phase("BLA submitted") == Phase.FILED
    assert ingest_llm._map_phase("something vague") == Phase.UNKNOWN


def test_keyless_returns_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert ingest_announcement("Big Pharma starts Phase 3", "PR:x") == []
