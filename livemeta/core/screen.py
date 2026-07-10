"""Search -> screen -> include: the eligibility gate that makes this a review.

A meta-analysis's credibility lives in the screening step: pooling every trial a
free-text search returns is a pooling engine, not a systematic review. This
module sits between retrieval and extraction and decides, per candidate, whether
it is eligible for the question.

Division of labour (CLAUDE.md):

1. A deterministic pre-filter removes what code can judge with certainty — a
   trial CT.gov explicitly records as non-interventional or non-randomized. It
   never excludes on *absent* metadata: benefit of the doubt passes the trial on
   to the clinical read (the demo fixtures carry no designModule and must stay
   eligible).
2. Claude reads each remaining trial's population / intervention / comparator
   against the question and judges include/exclude with a reason and a source
   quote — it judges, it never computes.

Honest degradation: with no key the clinical read cannot run, so trials that
clear the deterministic filter are *auto-included* and marked `by_claude=False`
with a visible reason. The funnel then shows the screen ran in reduced mode
rather than pretending it screened. The include/exclude *rule* is always code;
Claude only supplies the clinical judgment.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping

from pydantic import BaseModel

from .schema import EligibilityDecision, Provenance, Question

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

# How the batch clinical read is polled: the Messages Batch API usually completes
# within an hour (max 24h). We poll every 15s up to an hour before giving up and
# degrading to the serial read — a systematic-review search screens on the order
# of minutes-to-hours, so this is well within budget.
_BATCH_POLL_INTERVAL_S = 15.0
_BATCH_MAX_POLLS = 240

# JSON-schema mirror of `_ScreenJudged` for the Batch API path, which builds raw
# request params rather than using the `messages.parse` structured-output helper.
_SCREEN_SCHEMA = {
    "type": "object",
    "properties": {
        "eligible": {"type": "boolean"},
        "domain": {"type": "string"},
        "reason": {"type": "string"},
        "quote": {"type": "string"},
    },
    "required": ["eligible", "domain", "reason", "quote"],
    "additionalProperties": False,
}

_KEYLESS_REASON = (
    "Clinical eligibility screen unavailable (no model key) — auto-included, "
    "confirm manually."
)

_SYSTEM_HINT = (
    "You are screening a candidate randomized trial for a meta-analysis. Given the "
    "question's PICO and the trial's title and eligibility criteria, judge whether "
    "the trial is eligible — its population, intervention, and comparator must be "
    "close enough to the question that pooling it is clinically meaningful. Return "
    "`eligible` true/false, the PICO `domain` that fails when ineligible "
    "(population, intervention, comparator, or outcome), a one-sentence `reason`, "
    "and the exact `quote` from the eligibility text your call rests on. Judge "
    "only; do not compute anything. When in doubt, prefer to include."
)


class _ScreenJudged(BaseModel):
    """The per-trial eligibility judgment we ask Claude to return."""

    eligible: bool = True
    domain: str = ""  # population | intervention | comparator | outcome (when ineligible)
    reason: str = ""
    quote: str = ""


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


def _design(study: dict) -> tuple[str, str]:
    dm = study.get("protocolSection", {}).get("designModule", {})
    study_type = (dm.get("studyType") or "").upper()
    allocation = (dm.get("designInfo", {}) or {}).get("allocation") or ""
    return study_type, allocation.upper()


def _deterministic_reason(study: dict) -> str | None:
    """A reason to exclude on structured design alone, or None to pass on.

    Only fires when CT.gov *records* a design that disqualifies the trial —
    absent metadata is never a reason to exclude.
    """
    study_type, allocation = _design(study)
    if study_type and study_type != "INTERVENTIONAL":
        return f"Not an interventional trial (study type: {study_type.title()})."
    if allocation == "NON_RANDOMIZED":
        return "Not a randomized trial (allocation: non-randomized)."
    return None


def _source_url(ref_id: str) -> str:
    """Provenance link for a candidate — Europe PMC ids resolve to their article."""
    if ref_id.upper().startswith(("PMID:", "PMC")):
        return f"https://europepmc.org/article/{ref_id.replace(':', '/')}"
    return f"https://clinicaltrials.gov/study/{ref_id}"


def _trial_prompt(question: Question, study: dict) -> str:
    """The clinical-read prompt for one candidate, per its source shape.

    A ClinicalTrials.gov record is read from its title + eligibility criteria; a
    Europe PMC record (no `protocolSection`) is read from its title + abstract, so
    a published-literature candidate is screened on what it actually carries.
    """
    if study.get("source") == "europepmc":
        title = study.get("title", "")
        abstract = str(study.get("abstract", ""))[:1500]
        return (
            f"Question PICO: {question.pico.model_dump()}\n"
            f"Published trial: {title}\n"
            f"Abstract: {abstract}"
        )
    ps = study.get("protocolSection", {})
    ident = ps.get("identificationModule", {})
    elig = ps.get("eligibilityModule", {})
    return (
        f"Question PICO: {question.pico.model_dump()}\n"
        f"Trial: {ident.get('briefTitle', '')}\n"
        f"Eligibility criteria: {str(elig.get('eligibilityCriteria', ''))[:1500]}"
    )


def _decision_from_judged(nct: str, judged: _ScreenJudged) -> EligibilityDecision:
    """Turn Claude's per-trial judgment into an eligibility decision + provenance."""
    quote = (
        Provenance(trial_id=nct, snippet=judged.quote, source_url=_source_url(nct))
        if judged.quote
        else None
    )
    return EligibilityDecision(
        study_id=nct,
        decision="included" if judged.eligible else "excluded",
        reason=judged.reason,
        domain=(judged.domain or None) if not judged.eligible else None,
        quote=quote,
        by_claude=True,
    )


def _read_failed(nct: str) -> EligibilityDecision:
    """A failed or malformed clinical read must not silently include or exclude:
    auto-include so a real trial isn't dropped, but mark by_claude=False and route
    to manual review so the funnel shows the read did not complete."""
    return EligibilityDecision(
        study_id=nct,
        decision="included",
        reason="Eligibility read failed — auto-included, confirm manually.",
        by_claude=False,
    )


def _claude_screen(question: Question, nct: str, study: dict, client) -> EligibilityDecision:
    try:
        model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
        judged: _ScreenJudged = client.messages.parse(
            model=model,
            max_tokens=512,
            system=_SYSTEM_HINT,
            messages=[{"role": "user", "content": _trial_prompt(question, study)}],
            output_format=_ScreenJudged,
        ).parsed_output
        return _decision_from_judged(nct, judged)
    except Exception:
        return _read_failed(nct)


def _supports_batch(client) -> bool:
    """Whether the resolved client exposes the Messages Batch API."""
    return hasattr(getattr(client, "messages", None), "batches")


def _await_batch(client, batch):
    """Poll a submitted batch until it ends (or the poll budget is exhausted)."""
    for _ in range(_BATCH_MAX_POLLS):
        if getattr(batch, "processing_status", None) == "ended":
            return batch
        time.sleep(_BATCH_POLL_INTERVAL_S)
        batch = client.messages.batches.retrieve(batch.id)
    return batch


def _decision_from_batch_result(result) -> EligibilityDecision:
    """Parse one batch result into an eligibility decision (safe on any failure)."""
    nct = result.custom_id
    try:
        if result.result.type != "succeeded":
            return _read_failed(nct)
        content = result.result.message.content
        text = next(
            (b.text for b in content if getattr(b, "type", None) == "text"), ""
        )
        return _decision_from_judged(nct, _ScreenJudged.model_validate_json(text))
    except Exception:
        return _read_failed(nct)


def _screen_batch(
    question: Question, items: list[tuple[str, dict]], client
) -> dict[str, EligibilityDecision]:
    """Run the clinical read for many candidates as one Messages Batch.

    Same prompt, model, and structured judgment as the serial read — only the
    transport differs, at 50% of the per-token price. A whole-batch failure
    degrades to the serial read so screening still completes.
    """
    model = os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL)
    requests = [
        {
            "custom_id": nct,
            "params": {
                "model": model,
                "max_tokens": 512,
                "system": _SYSTEM_HINT,
                "messages": [{"role": "user", "content": _trial_prompt(question, study)}],
                "output_config": {
                    "format": {"type": "json_schema", "schema": _SCREEN_SCHEMA}
                },
            },
        }
        for nct, study in items
    ]
    try:
        batch = _await_batch(client, client.messages.batches.create(requests=requests))
        out: dict[str, EligibilityDecision] = {}
        for result in client.messages.batches.results(batch.id):
            out[result.custom_id] = _decision_from_batch_result(result)
        for nct, _study in items:  # any id absent from the results is read-failed
            out.setdefault(nct, _read_failed(nct))
        return out
    except Exception:
        return {nct: _claude_screen(question, nct, study, client) for nct, study in items}


def _resolve_batch(batch: bool | None) -> bool:
    """Batch screening is opt-in: explicit flag wins, else the env toggle.

    Off by default so the live, streamed demo keeps its low latency; on (via
    `batch=True` or `LIVEMETA_SCREEN_BATCH=1`) for a large systematic search,
    where the Batch API halves the per-token screening cost.
    """
    if batch is not None:
        return batch
    return os.environ.get("LIVEMETA_SCREEN_BATCH", "").strip().lower() in ("1", "true", "yes")


def screen_candidates(
    question: Question,
    studies_by_id: Mapping[str, dict],
    llm_client=None,
    overrides: Mapping[str, EligibilityDecision] | None = None,
    batch: bool | None = None,
) -> list[EligibilityDecision]:
    """Screen each fetched candidate for eligibility; one decision per study.

    Decisions follow the question's `trial_ids` order (then any extra fetched
    ids), so the PRISMA funnel and the ledger read deterministically. A
    deterministically-excluded trial never reaches the model, and only the trials
    that need the clinical read are sent to it.

    `overrides` are a reviewer's authoritative include/exclude calls, keyed by
    study id: where one exists it replaces the automated judgment outright (the
    human confirming or overriding the screen), so a re-run honours the sign-off.

    `batch` (or the `LIVEMETA_SCREEN_BATCH` env toggle) runs the clinical read as
    a single Messages Batch instead of one live call per candidate — same
    decisions, 50% of the per-token cost — for a large multi-source search.
    """
    overrides = overrides or {}
    ordered = [tid for tid in question.trial_ids if tid in studies_by_id]
    ordered += [tid for tid in studies_by_id if tid not in set(ordered)]

    client = _resolve_client(llm_client)

    # First pass: apply reviewer overrides and the deterministic design filter;
    # collect the trials that still need a clinical read.
    decisions_by_id: dict[str, EligibilityDecision] = {}
    to_read: list[str] = []
    for nct in ordered:
        override = overrides.get(nct)
        if override is not None:
            decisions_by_id[nct] = override
            continue

        study = studies_by_id[nct]
        det_reason = _deterministic_reason(study)
        if det_reason is not None:
            decisions_by_id[nct] = EligibilityDecision(
                study_id=nct, decision="excluded", reason=det_reason, domain="design"
            )
            continue

        if client is None:
            decisions_by_id[nct] = EligibilityDecision(
                study_id=nct, decision="included", reason=_KEYLESS_REASON
            )
            continue

        to_read.append(nct)

    # Clinical read: one batch, or one live call per trial.
    if to_read:
        if _resolve_batch(batch) and _supports_batch(client):
            judged = _screen_batch(
                question, [(n, studies_by_id[n]) for n in to_read], client
            )
            decisions_by_id.update(judged)
        else:
            for nct in to_read:
                decisions_by_id[nct] = _claude_screen(
                    question, nct, studies_by_id[nct], client
                )

    return [decisions_by_id[nct] for nct in ordered]
