"""ClinicalTrials.gov v2 API client.

Primary data source: returns structured, arm-level results, which avoids PDF
parsing. https://clinicaltrials.gov/data-api/api
"""

from __future__ import annotations

import httpx

BASE_URL = "https://clinicaltrials.gov/api/v2"

# ClinicalTrials.gov 403s the default python-httpx User-Agent from datacenter
# IPs (e.g. Railway). A browser-like UA is required for the deployed backend.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class ClinicalTrialsClient:
    def __init__(self, base_url: str = BASE_URL, timeout: float = 40.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def fetch_study(self, nct_id: str) -> dict:
        """Full study record (protocol + results) for one trial."""
        resp = httpx.get(
            f"{self._base}/studies/{nct_id}", headers=_HEADERS, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def search_studies(self, query: str, page_size: int = 1000) -> list[dict]:
        """Search by free-text term; return [{nct_id, title}]."""
        resp = httpx.get(
            f"{self._base}/studies",
            params={
                "query.term": query,
                "pageSize": page_size,
                "fields": "protocolSection.identificationModule",
            },
            headers=_HEADERS,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        hits = []
        for study in resp.json().get("studies", []):
            ident = study.get("protocolSection", {}).get("identificationModule", {})
            hits.append(
                {"nct_id": ident.get("nctId", ""), "title": ident.get("briefTitle", "")}
            )
        return hits

    # Modules needed to place a drug in the competitive pipeline: who sponsors it,
    # what phase, its status and dated milestones, the drug name, the indication.
    _PIPELINE_FIELDS = ",".join(
        "protocolSection." + m
        for m in (
            "identificationModule",
            "sponsorCollaboratorsModule",
            "designModule",
            "statusModule",
            "armsInterventionsModule",
            "conditionsModule",
        )
    )

    def search_pipeline(self, query: str, page_size: int = 1000) -> list[dict]:
        """Search returning the raw study records (with pipeline modules).

        The competitive-intelligence sibling of `search_studies`: it keeps the
        full structured record so the CI parser can read sponsor / phase / status
        / dates / interventions, which `search_studies` deliberately strips.
        """
        resp = httpx.get(
            f"{self._base}/studies",
            params={
                "query.term": query,
                "pageSize": page_size,
                "fields": self._PIPELINE_FIELDS,
            },
            headers=_HEADERS,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json().get("studies", [])
