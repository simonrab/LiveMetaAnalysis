"""Versioned snapshot store for review runs.

A deliberately minimal JSON store: one file per question id holding an ordered
list of ReviewResult snapshots. This is the Slice-2 stand-in for Slice 5's
SQLite; the interface (save / load_latest / list_versions) is kept stable so the
backend can be swapped without touching callers. The version list is also the
audit-trail history the living layer reads.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .schema import ReviewResult

_DEFAULT_DIR = ".livemeta_data"
_SAFE = re.compile(r"[^A-Za-z0-9_-]+")


class SnapshotStore:
    def __init__(self, data_dir: str | Path | None = None):
        base = data_dir or os.environ.get("LIVEMETA_DATA_DIR", _DEFAULT_DIR)
        self._dir = Path(base)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, question_id: str) -> Path:
        return self._dir / f"{_SAFE.sub('_', question_id)}.json"

    def _read(self, question_id: str) -> list[dict]:
        path = self._path(question_id)
        if not path.exists():
            return []
        return json.loads(path.read_text()).get("snapshots", [])

    def save_snapshot(self, result: ReviewResult) -> int:
        """Append a snapshot for its question; return the new version number."""
        question_id = result.question.id
        snapshots = self._read(question_id)
        version = len(snapshots) + 1
        snapshots.append({"version": version, "result": result.model_dump(mode="json")})
        self._path(question_id).write_text(
            json.dumps({"question_id": question_id, "snapshots": snapshots}, indent=2)
        )
        return version

    def load_latest(self, question_id: str) -> ReviewResult | None:
        snapshots = self._read(question_id)
        if not snapshots:
            return None
        return ReviewResult.model_validate(snapshots[-1]["result"])

    def list_versions(self, question_id: str) -> list[int]:
        return [s["version"] for s in self._read(question_id)]
