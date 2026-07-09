"""Reconciliation: dated events -> a competitive matrix, as of a point in time.

The trust-bearing deterministic step. Time-travel is a pure filter; the most
advanced *sourced* stage wins; conflicting sources are flagged, never silently
resolved.
"""

from livemeta.core.ci.reconcile import assemble_landscape
from livemeta.core.ci.schema import (
    DevelopmentEvent,
    EventType,
    Phase,
    SourceType,
)
from livemeta.core.schema import Provenance


def _ev(asset, indication, phase, date, source=SourceType.CTGOV, etype=EventType.TRIAL_START):
    return DevelopmentEvent(
        asset_name=asset,
        indication=indication,
        phase=phase,
        date=date,
        event_type=etype,
        source_type=source,
        provenance=[Provenance(trial_id="NCT_x", snippet=f"{asset} {phase.value}")],
    )


def test_groups_by_asset_and_indication_into_cells():
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01"),
        _ev("DrugB", "T2D", Phase.PHASE_3, "2017-01-01"),
    ]
    ls = assemble_landscape(events, as_of=None, links={})
    assert set(ls.assets) == {"DrugA", "DrugB"}
    assert ls.indications == ["T2D"]
    assert len(ls.cells) == 2


def test_most_advanced_phase_wins_within_a_group():
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01"),
        _ev("DrugA", "T2D", Phase.PHASE_3, "2018-01-01"),
    ]
    (cell,) = assemble_landscape(events, as_of=None, links={}).cells
    assert cell.current_phase == Phase.PHASE_3


def test_as_of_filter_reconstructs_an_earlier_pipeline():
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01"),
        _ev("DrugA", "T2D", Phase.PHASE_3, "2018-01-01"),
    ]
    (cell,) = assemble_landscape(events, as_of="2017-01-01", links={}).cells
    assert cell.current_phase == Phase.PHASE_2  # the Phase 3 event is in the future


def test_as_of_before_any_event_drops_the_cell():
    events = [_ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01")]
    assert assemble_landscape(events, as_of="2015-01-01", links={}).cells == []


def test_undated_events_excluded_when_as_of_is_set():
    events = [_ev("DrugA", "T2D", Phase.PHASE_3, None)]
    assert assemble_landscape(events, as_of="2020-01-01", links={}).cells == []
    # ...but included when no as_of is given (we can't prove it is in the future).
    assert assemble_landscape(events, as_of=None, links={}).cells


def test_conflicting_sources_are_flagged_not_resolved():
    # A 2019 press release claims approval, but CT.gov still shows Phase 3 in
    # 2020 — a genuine contradiction about the current state, not progression.
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_3, "2020-01-01", source=SourceType.CTGOV),
        _ev(
            "DrugA",
            "T2D",
            Phase.APPROVED,
            "2019-01-01",
            source=SourceType.ANNOUNCEMENT,
            etype=EventType.APPROVAL,
        ),
    ]
    (cell,) = assemble_landscape(events, as_of=None, links={}).cells
    assert cell.conflict is True
    assert cell.conflict_note


def test_progression_across_sources_is_not_a_conflict():
    # CT.gov Phase 3 in 2018, then an approval announcement in 2019: the drug
    # advanced — later and more advanced is normal, not a contradiction.
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_3, "2018-01-01", source=SourceType.CTGOV),
        _ev(
            "DrugA",
            "T2D",
            Phase.APPROVED,
            "2019-01-01",
            source=SourceType.ANNOUNCEMENT,
            etype=EventType.APPROVAL,
        ),
    ]
    (cell,) = assemble_landscape(events, as_of=None, links={}).cells
    assert cell.conflict is False
    assert cell.current_phase == Phase.APPROVED


def test_agreeing_sources_do_not_flag_conflict():
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_3, "2018-01-01", source=SourceType.CTGOV),
        _ev(
            "DrugA",
            "T2D",
            Phase.PHASE_3,
            "2019-01-01",
            source=SourceType.ANNOUNCEMENT,
            etype=EventType.READOUT,
        ),
    ]
    (cell,) = assemble_landscape(events, as_of=None, links={}).cells
    assert cell.conflict is False


def test_latest_event_and_provenance_carried_onto_cell():
    events = [
        _ev("DrugA", "T2D", Phase.PHASE_2, "2016-01-01"),
        _ev("DrugA", "T2D", Phase.PHASE_3, "2018-01-01"),
    ]
    (cell,) = assemble_landscape(events, as_of=None, links={}).cells
    assert cell.latest_event.date == "2018-01-01"
    assert cell.provenance  # traceable to a source
