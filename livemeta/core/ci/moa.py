"""Cluster a condition's assets by mechanism of action, with class-level evidence.

`Asset.drug_class` is not populated by CT.gov, so mechanism must be *inferred*.
Mirroring the sub-population reader: Claude names the class when a key is present,
and a deterministic **INN-stem heuristic** (the WHO naming convention — "-glutide"
= GLP-1 agonist, "-flozin" = SGLT2 inhibitor, "-mab" = monoclonal antibody, …) is
the offline fallback. When neither is confident the asset is "unclassified" — a
real bucket, never a fabricated class. Each result is cached per asset.
"""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable

from pydantic import BaseModel, Field

from .link import plain_evidence
from .schema import EvidenceBadge, MoaCluster, MoaLandscape

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
UNCLASSIFIED = "unclassified"

# WHO INN stems → class label. Ordered: more specific suffixes first.
_STEMS: list[tuple[str, str]] = [
    ("glutide", "GLP-1 receptor agonists"),
    ("gliptin", "DPP-4 inhibitors"),
    ("gliflozin", "SGLT2 inhibitors"),
    ("flozin", "SGLT2 inhibitors"),
    ("ciclib", "CDK4/6 inhibitors"),
    ("parib", "PARP inhibitors"),
    ("tinib", "Kinase inhibitors"),
    ("sartan", "Angiotensin receptor blockers"),
    ("prazole", "Proton-pump inhibitors"),
    ("statin", "Statins"),
    ("cel", "Cell therapies"),
    ("mab", "Monoclonal antibodies"),
    ("tide", "Peptide analogues"),
]

_SYSTEM_HINT = (
    "You are classifying one drug by its mechanism of action / pharmacologic class. "
    "Return a short canonical class label (e.g. 'GLP-1 receptor agonist', 'SGLT2 "
    "inhibitor', 'amylin analogue', 'anti-amyloid monoclonal antibody'). Set "
    "found=false and confidence='low' if you are not reasonably sure — do NOT guess "
    "a class. Quote the basis (INN stem or known mechanism) in source_snippet."
)


class _MoaRead(BaseModel):
    found: bool = False
    confidence: str = "low"  # high | moderate | low
    drug_class: str = ""
    source_snippet: str = ""


def _stem_class(asset_name: str) -> str:
    name = asset_name.strip().lower()
    for stem, label in _STEMS:
        if name.endswith(stem):
            return label
    return UNCLASSIFIED


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


def infer_drug_class(
    asset_name: str, interventions: list[str] | None = None, *, llm_client=None
) -> str:
    """Best available class for an asset: Claude when confident, else INN stem."""
    client = _resolve_client(llm_client)
    if client is not None:
        try:
            prompt = f"Drug: {asset_name}\nInterventions/context: {', '.join(interventions or [])}"
            read: _MoaRead = client.messages.parse(
                model=os.environ.get("LIVEMETA_LLM_MODEL", _DEFAULT_MODEL),
                max_tokens=512,
                system=_SYSTEM_HINT,
                messages=[{"role": "user", "content": prompt}],
                output_format=_MoaRead,
            ).parsed_output
            if read.found and read.confidence != "low" and read.drug_class.strip():
                return read.drug_class.strip()
        except Exception:
            pass
    return _stem_class(asset_name)


def _class_evidence(badges: list[EvidenceBadge]) -> EvidenceBadge | None:
    """A representative badge for the class: a committed pool wins, then a gate."""
    pooled = [b for b in badges if b.state == "pooled"]
    if pooled:
        # The most decisive committed pool (significant first, then any).
        significant = [b for b in pooled if (b.conclusion or "").startswith("significant")]
        return significant[0] if significant else pooled[0]
    gate = [b for b in badges if b.state == "gate_open"]
    return gate[0] if gate else (badges[0] if badges else None)


def moa_landscape(
    store,
    condition: str,
    *,
    search: Callable[[str], list[dict]] | None = None,
    llm_client=None,
) -> MoaLandscape:
    """Group a condition's landscape cells by inferred mechanism of action."""
    from .service import get_landscape

    landscape = get_landscape(store, condition, search_pipeline=search)
    assets = landscape.assets

    classes = store.load_moa(assets)
    fresh: dict[str, str] = {}
    for asset in assets:
        if asset not in classes:
            cls = infer_drug_class(asset, [], llm_client=llm_client)
            fresh[asset] = cls
            classes[asset] = cls
    if fresh:
        # One transaction — a cold obesity landscape has ~1k assets.
        store.save_moa_many(fresh)

    # Bucket cells by class.
    buckets: dict[str, list] = {}
    for cell in landscape.cells:
        cls = classes.get(cell.asset_name, UNCLASSIFIED)
        buckets.setdefault(cls, []).append(cell)

    clusters: list[MoaCluster] = []
    for cls, cells in buckets.items():
        badges = [c.evidence for c in cells if c.evidence is not None]
        rep = _class_evidence(badges)
        clusters.append(
            MoaCluster(
                drug_class=cls,
                label="Unclassified" if cls == UNCLASSIFIED else cls,
                assets=sorted({c.asset_name for c in cells}),
                program_count=len(cells),
                stage_distribution=dict(Counter(c.current_phase.value for c in cells)),
                plain_summary=plain_evidence(rep),
                evidence=rep,
            )
        )

    # Largest field first; the "unclassified" bucket always sinks to the bottom.
    clusters.sort(key=lambda c: (c.drug_class == UNCLASSIFIED, -c.program_count, c.label))

    return MoaLandscape(condition=condition, clusters=clusters, notes=list(landscape.notes))
