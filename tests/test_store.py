"""Snapshot store: versioned ReviewResult persistence keyed by question id.

Minimal JSON store standing in for Slice 5's SQLite; the version list is the
audit-trail history.
"""

from livemeta.core.schema import PICO, Question, ReviewDecision, ReviewResult, RobDecision
from livemeta.core.store import SnapshotStore


def _review(summary: str, qid: str = "q-demo") -> ReviewResult:
    q = Question(
        id=qid,
        text="demo",
        pico=PICO(population="p", intervention="i", comparator="c", outcome="o"),
    )
    return ReviewResult(question=q, summary=summary)


def test_save_increments_versions_and_load_latest_returns_newest(tmp_path):
    store = SnapshotStore(tmp_path)

    v1 = store.save_snapshot(_review("first"))
    v2 = store.save_snapshot(_review("second"))

    assert v1 == 1
    assert v2 == 2
    assert store.list_versions("q-demo") == [1, 2]

    latest = store.load_latest("q-demo")
    assert latest is not None
    assert latest.summary == "second"


def test_load_latest_missing_returns_none(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_latest("does-not-exist") is None
    assert store.list_versions("does-not-exist") == []


def test_list_questions_returns_saved_question_ids(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.list_questions() == []

    store.save_snapshot(_review("a", qid="glp1-mace"))
    store.save_snapshot(_review("b", qid="sglt2-hf"))

    assert sorted(store.list_questions()) == ["glp1-mace", "sglt2-hf"]


def test_decisions_round_trip_and_default_empty(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_decisions("q-demo") == []

    store.save_snapshot(_review("first"))
    store.save_decision(
        "q-demo", ReviewDecision(study_id="NCT01", decision="flagged", reason="bad arm")
    )
    store.save_decision("q-demo", ReviewDecision(study_id="NCT02", decision="confirmed"))

    decisions = store.load_decisions("q-demo")
    assert {d.study_id: d.decision for d in decisions} == {
        "NCT01": "flagged",
        "NCT02": "confirmed",
    }
    # A later decision on the same trial supersedes the earlier one.
    store.save_decision("q-demo", ReviewDecision(study_id="NCT01", decision="confirmed"))
    decisions = store.load_decisions("q-demo")
    by_id = {d.study_id: d.decision for d in decisions}
    assert by_id["NCT01"] == "confirmed"

    # Decisions live alongside snapshots without clobbering the version history.
    assert store.list_versions("q-demo") == [1]


def test_rob_decisions_round_trip_latest_per_domain_wins(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.load_rob_decisions("q-demo") == []

    store.save_snapshot(_review("first"))
    store.save_rob_decision("q-demo", RobDecision(study_id="NCT01", domain_key="D1"))
    store.save_rob_decision("q-demo", RobDecision(study_id="NCT01", domain_key="D2"))
    store.save_rob_decision(
        "q-demo", RobDecision(study_id="NCT01", domain_key="D1", reason="re-checked")
    )

    decisions = store.load_rob_decisions("q-demo")
    # Two distinct (study, domain) sign-offs; the D1 re-check superseded the first.
    keys = {(d.study_id, d.domain_key) for d in decisions}
    assert keys == {("NCT01", "D1"), ("NCT01", "D2")}
    d1 = next(d for d in decisions if d.domain_key == "D1")
    assert d1.reason == "re-checked"
    # RoB sign-offs don't disturb the trial decision list or the version history.
    assert store.load_decisions("q-demo") == []
    assert store.list_versions("q-demo") == [1]
