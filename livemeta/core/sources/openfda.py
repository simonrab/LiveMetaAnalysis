"""openFDA drugsfda client — regulatory approvals for an asset.

Structured, authoritative: drug, sponsor, application number, brand(s), approval
date, marketing status. openFDA does NOT return the approved *indication* text
(that lives in the label PDF), so `indication_approx` is left None — approvals are
reported without over-claiming what they were approved *for*.
"""

from __future__ import annotations

import re

import httpx

from ..ci.schema import RegulatoryApproval
from ..schema import Provenance

BASE_URL = "https://api.fda.gov/drug/drugsfda.json"

# Legal-form and generic-industry words carry no identity, so they are dropped
# when matching a CT.gov lead-sponsor name against openFDA's `sponsor_name`
# (e.g. "Novo Nordisk A/S" -> {novo, nordisk}). Prevents a bare "Inc"/"Pharma"
# from pulling in unrelated companies.
_SPONSOR_STOPWORDS = frozenset(
    {
        "inc", "incorporated", "corp", "corporation", "co", "company", "ltd",
        "limited", "llc", "plc", "sa", "ag", "gmbh", "as", "nv", "bv", "spa",
        "pharmaceuticals", "pharmaceutical", "pharma", "pharms", "the", "and",
        "group", "holdings", "international",
    }
)


def _sponsor_tokens(sponsor: str) -> list[str]:
    """The identity-bearing lowercased tokens of a sponsor name (>=3 chars, no
    legal/industry stopwords). Empty when the name is all stopwords."""
    return [
        t
        for t in re.split(r"[^a-z0-9]+", sponsor.lower())
        if len(t) >= 3 and t not in _SPONSOR_STOPWORDS
    ]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


def _fmt_date(raw: str | None) -> str | None:
    """openFDA dates are YYYYMMDD -> ISO YYYY-MM-DD."""
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"


def _approval_date(result: dict) -> str | None:
    """Earliest 'AP' (approved) submission date across a result's submissions."""
    dates = [
        _fmt_date(s.get("submission_status_date"))
        for s in result.get("submissions", [])
        if s.get("submission_status") == "AP"
    ]
    dates = [d for d in dates if d]
    return min(dates) if dates else None


def _brand_names(result: dict) -> list[str]:
    names: list[str] = []
    for p in result.get("products", []):
        name = (p.get("brand_name") or "").strip()
        if name and name not in names:
            names.append(name)
    for name in result.get("openfda", {}).get("brand_name", []):
        if name and name not in names:
            names.append(name)
    return names


def _marketing_status(result: dict) -> str | None:
    products = result.get("products", [])
    return products[0].get("marketing_status") if products else None


def _drugs_at_fda_url(application_number: str) -> str:
    """The human-facing Drugs@FDA overview page for an application, keyed by the
    numeric part of the application number (e.g. NDA209637 -> ApplNo=209637).
    Falls back to the Drugs@FDA landing page when no digits are present."""
    appl_no = "".join(c for c in application_number if c.isdigit())
    if not appl_no:
        return "https://www.accessdata.fda.gov/scripts/cder/daf/"
    return (
        "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
        f"?event=overview.process&ApplNo={appl_no}"
    )


def _generic_name(result: dict) -> str | None:
    """The record's generic (INN) name, title-cased, when openFDA carries one."""
    names = result.get("openfda", {}).get("generic_name") or []
    return names[0].title() if names and names[0] else None


def _result_to_approval(result: dict, drug: str) -> RegulatoryApproval | None:
    """Map one drugsfda result to a RegulatoryApproval (None if it has no app no.)."""
    app_no = result.get("application_number", "")
    if not app_no:
        return None
    brands = _brand_names(result)
    return RegulatoryApproval(
        drug=drug,
        sponsor=result.get("sponsor_name"),
        application_number=app_no,
        brand_names=brands,
        approval_date=_approval_date(result),
        marketing_status=_marketing_status(result),
        indication_approx=None,
        provenance=[
            Provenance(
                trial_id=app_no,
                snippet=f"{drug} — {app_no} ({', '.join(brands) or 'no brand'})",
                source_url=_drugs_at_fda_url(app_no),
                field="openfda.drugsfda",
            )
        ],
    )


class OpenFdaClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0):
        self._base = base_url
        self._timeout = timeout

    def _search(self, expr: str, limit: int) -> list[dict]:
        """Run a drugsfda search, degrading a 404/HTTP error to no results."""
        try:
            resp = httpx.get(
                self._base,
                params={"search": expr, "limit": limit},
                headers=_HEADERS,
                timeout=self._timeout,
            )
        except httpx.HTTPError:
            return []
        if resp.status_code == 404:  # openFDA returns 404 when nothing matches
            return []
        resp.raise_for_status()
        return resp.json().get("results", [])

    def approvals_for(self, drug: str, limit: int = 20) -> list[RegulatoryApproval]:
        """Regulatory approvals whose generic name matches `drug` (empty on miss)."""
        results = self._search(f'openfda.generic_name:"{drug}"', limit)
        approvals = [_result_to_approval(r, drug) for r in results]
        return [a for a in approvals if a is not None]

    def approvals_by_sponsor(
        self, sponsor: str, limit: int = 100
    ) -> list[RegulatoryApproval]:
        """Every approval held by a sponsor, for the company pipeline view.

        Sponsor identity is messy: CT.gov says "Novo Nordisk A/S", openFDA says
        "NOVO NORDISK INC". openFDA also matches `sponsor_name` tokens with OR
        semantics, so a token search pulls in near-misses (a stray "NOVO", a
        "ZEALAND PHARMA"). To stay trustworthy — never show another company's
        approvals — we search on the identity tokens, then keep only records whose
        `sponsor_name` actually contains the most distinctive (longest) token.
        The drug label is derived per record (generic, else brand, else sponsor)
        since no single drug was searched. Empty on a miss or unreachable openFDA."""
        tokens = _sponsor_tokens(sponsor)
        expr = " ".join(tokens) if tokens else f'"{sponsor}"'
        key = max(tokens, key=len) if tokens else sponsor.lower()

        approvals: list[RegulatoryApproval] = []
        for result in self._search(expr, limit):
            name = (result.get("sponsor_name") or "").lower()
            if key not in name:
                continue  # deterministic precision gate: reject near-miss sponsors
            brands = _brand_names(result)
            drug = _generic_name(result) or (brands[0].title() if brands else sponsor)
            approval = _result_to_approval(result, drug)
            if approval is not None:
                approvals.append(approval)
        return approvals
