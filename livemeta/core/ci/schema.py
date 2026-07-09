"""Schema for the competitive-intelligence layer.

These models *reference* the meta-analysis by `question_id` and reuse its
`Provenance` atom, so a competitive claim ("Phase 3") and a pooled effect
("HR 0.86") carry the same kind of source snippet. Everything here is additive:
the meta-analysis schema is untouched, and the GLP-1 HR demo is unaffected.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ..schema import Provenance


class Phase(str, Enum):
    """Development stage, ordered by `PHASE_RANK` for "most advanced" roll-ups."""

    PRECLINICAL = "preclinical"
    PHASE_1 = "phase_1"
    PHASE_1_2 = "phase_1_2"
    PHASE_2 = "phase_2"
    PHASE_2_3 = "phase_2_3"
    PHASE_3 = "phase_3"
    PHASE_4 = "phase_4"
    FILED = "filed"
    APPROVED = "approved"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


# Ordering for reconciliation: a later, more-advanced stage wins. WITHDRAWN and
# UNKNOWN sort below everything so a real stage is always preferred over them.
PHASE_RANK: dict[Phase, int] = {
    Phase.WITHDRAWN: -2,
    Phase.UNKNOWN: -1,
    Phase.PRECLINICAL: 0,
    Phase.PHASE_1: 1,
    Phase.PHASE_1_2: 2,
    Phase.PHASE_2: 3,
    Phase.PHASE_2_3: 4,
    Phase.PHASE_3: 5,
    Phase.PHASE_4: 6,
    Phase.FILED: 7,
    Phase.APPROVED: 8,
}


def phase_rank(phase: Phase) -> int:
    return PHASE_RANK.get(phase, -1)


class SourceType(str, Enum):
    CTGOV = "ctgov"
    ANNOUNCEMENT = "announcement"
    FILING = "filing"


class EventType(str, Enum):
    TRIAL_START = "trial_start"
    TRIAL_STATUS = "trial_status"
    READOUT = "readout"
    FILING = "filing"
    APPROVAL = "approval"
    ANNOUNCEMENT = "announcement"


class Asset(BaseModel):
    """A compound's identity, with the source it was read from."""

    name: str
    aliases: list[str] = Field(default_factory=list)
    sponsor: str | None = None
    sponsor_class: str | None = None  # INDUSTRY | NIH | OTHER (CT.gov leadSponsor.class)
    drug_class: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class DevelopmentEvent(BaseModel):
    """The dated, sourced atom of the pipeline time series.

    Every state a drug has been in is one of these, so "the pipeline as of date T"
    is a pure filter over events. Each carries `provenance` — no stage claim
    without a source snippet.
    """

    asset_name: str
    indication: str
    line_of_therapy: str | None = None
    phase: Phase = Phase.UNKNOWN
    status: str | None = None
    event_type: EventType = EventType.TRIAL_STATUS
    date: str | None = None  # ISO date (YYYY-MM-DD); None when the source omits it
    source_type: SourceType = SourceType.CTGOV
    sponsor: str | None = None
    sponsor_class: str | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class ExtractedDevelopmentEvent(BaseModel):
    """Claude's structured read of a free-text announcement/filing.

    The sibling of `extract_text.ExtractedEffect`: Claude reports what the
    document says (with the exact snippet and a self-reported confidence); code
    maps it to a `DevelopmentEvent` and drops/flags anything low-confidence. The
    model never asserts a stage the text does not state.
    """

    found: bool = False
    confidence: str = "low"  # high | moderate | low
    source_snippet: str = ""

    asset_name: str = ""
    sponsor: str | None = None
    indication: str = ""
    line_of_therapy: str | None = None
    phase: str = "unknown"  # free string; mapped to Phase in code
    event_type: str = "announcement"
    date: str | None = None


class EvidenceBadge(BaseModel):
    """The living pooled-evidence summary denormalized onto a landscape cell.

    `state` distinguishes the three honest outcomes of the evidence layer so a
    cell never shows a fabricated number: a committed pool, a pool withheld
    pending a homogeneity confirmation, or an abstention (too few / no data).
    """

    question_id: str
    measure: str = "HR"
    state: str = "abstained"  # pooled | gate_open | abstained
    estimate: float | None = None
    ci_low: float | None = None
    ci_high: float | None = None
    grade_certainty: str | None = None
    conclusion: str | None = None  # human-readable, e.g. "significant reduction"
    version: int | None = None
    k: int = 0


class LandscapeCell(BaseModel):
    """One asset × indication(× line) rollup, as of a date."""

    asset_name: str
    indication: str
    line_of_therapy: str | None = None
    current_phase: Phase = Phase.UNKNOWN
    status: str | None = None
    sponsor: str | None = None
    sponsor_class: str | None = None
    latest_event: DevelopmentEvent | None = None
    conflict: bool = False
    conflict_note: str | None = None
    question_id: str | None = None
    evidence: EvidenceBadge | None = None
    provenance: list[Provenance] = Field(default_factory=list)


class Landscape(BaseModel):
    """The assembled competitive matrix for a condition, at one point in time.

    The matrix axes are `assets` (rows) × `indications` (columns) — the two the
    structured CT.gov record actually populates. Line of therapy, when a source
    supplies it, lives on the cell; it is not the column axis because CT.gov
    rarely states it.
    """

    condition: str
    as_of: str | None = None
    assets: list[str] = Field(default_factory=list)
    indications: list[str] = Field(default_factory=list)
    cells: list[LandscapeCell] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
