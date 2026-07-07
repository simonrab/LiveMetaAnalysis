"""Snapshot store: versioned ReviewResult persistence keyed by question id.

Minimal JSON store standing in for Slice 5's SQLite; the version list is the
audit-trail history.
"""

from livemeta.core.schema import PICO, Question, ReviewResult
from livemeta.core.store import SnapshotStore


def _review(summary: str) -> ReviewResult:
    q = Question(
        id="q-demo",
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
