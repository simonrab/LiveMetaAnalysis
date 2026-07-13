# Strata — Build Context

Strata (tagline "Living evidence") is a living meta-analysis tool. Internal build name: "Living Meta-Analysis Tool"; same thing.

## What it does
The user asks a research question in PICO form for one outcome. Strata finds the trials, extracts the evidence with full provenance, and pools it into a single auditable answer: an effect estimate with confidence interval, a forest plot, heterogeneity measures, and a plain-language summary. Every number traces to its source trial and snippet. When a new trial reads out, the tool re-runs and flags whether the estimate or conclusion changed, so the evidence never goes stale.

## Core design principle
Divide the labour by what each part is reliable at.
- Claude reads and structures evidence. It is strong at reading, weak at arithmetic.
- A validated statistics library does all pooling and math. Never let the model compute pooled estimates.
- Every number traces to a source trial and the exact snippet it came from.
- The tool abstains rather than inventing precision when data is thin or heterogeneity is high.

**The rule that holds it together:** pool only numbers that trace to a source and pass validation. Report what was excluded and why. Refuse a confident pooled estimate when heterogeneity is high or data is thin.

## Engineering practice: TDD and BDD (mandatory)
All code, backend and frontend, is written test-first. No production module before its failing test.
- TDD: red, green, refactor. BDD: describe behaviour as Given/When/Then scenarios that become executable tests, covering the pipeline spine and user journeys.
- Backend: `pytest` plus `pytest-bdd` for Gherkin `.feature` scenarios. Frontend: Vitest plus React Testing Library.
- The deterministic validation gate and the stats engine get the heaviest coverage — they are the trust story.

## Architecture
Three thin front ends over one shared core (`livemeta/core/pipeline.py`), so they cannot diverge:
- **MCP server** (`livemeta/mcp/server.py`) so Claude can drive the workflow.
- **Web UI** — runs the whole review end to end: ask, watch the pipeline, inspect the evidence ledger, verify extractions, review risk of bias and GRADE, read the report and forest plot. A first-class deliverable, built against the reference designs in `stitch_livemeta_precision_evidence_system/`.
- **CLI** (`livemeta/cli/`, the `livemeta` command) with full parity: run, search, report, history, living update, and every human-in-the-loop decision. ASCII forest plot, matplotlib PNG export (`--plot`), `--json` on every subcommand, offline against recorded fixtures (`--fixtures`).

Core MCP tools: `search_trials(pico, outcome)`, `extract_effects(trial_id)`, `validate(extractions)`, `pool(validated_effects)`, `update(question_id, new_trial)`. (Market-intelligence tools are listed below.)

## Data sources
- **ClinicalTrials.gov v2** (https://clinicaltrials.gov/data-api/api). Primary, always on. Structured arm-level results, which avoids PDF parsing.
- **Europe PMC / PubMed** (https://europepmc.org/RestfulWebService). Opt-in, off by default. Published trials and abstracts surface for review but never enter the pool — only CT.gov structured results are pooled.
- **openFDA** (https://open.fda.gov/) US drug approvals. Opt-in, off by default; feeds the market-intelligence layer only, never the pool.
- A source is opt-in when a caller names it (`sources=ctgov,pubmed,openfda` per request, or `--enable-pubmed`/`--enable-fda` on the CLI); the live PubMed/openFDA client is provisioned only then. See `explicitly_selected` in `livemeta/core/ci/schema.py`.
- Full text only when structured effect data is absent.

## Pipeline
1. Parse the question into PICO and one outcome. Claude does this.
2. Retrieve candidate trials from CT.gov v2 by default; opt in to Europe PMC to also search published literature.
3. Extract effect data into a fixed schema. Binary: events and totals per arm. Continuous: mean, SD, n per arm. Every value carries source trial ID and snippet.
4. Validate deterministically before any pooling.
5. Assess risk of bias per trial (RoB 2) and rate certainty (GRADE). Claude does a first-pass reading, a human confirms.
6. Pool with a validated library: pooled effect, confidence interval, I², τ².
7. Output a forest plot, plain-language summary, heterogeneity warnings, and a leave-one-out sensitivity check.
8. Living layer: when a new trial lands, re-run and flag whether the estimate or conclusion changed.

## Extraction strategy
Safety-first tiering — fail safely on the messy tail rather than pool bad numbers.
- Take structured arm-level CT.gov results first. Drop to full text only for effect data not in a structured field.
- In full text, parse tables as tables, not a flattened blob. Most effect data lives in tables.
- Require provenance: source trial ID and the exact sentence or table cell. If a value is not clearly present, return null and flag — no silent inference or back-calculation.
- Low-confidence or conflicting extractions surface for quick human review before entering the pool. This is the audit trail, not a workaround.

## Statistics
Use a validated library, never hand-rolled pooling. If a required method is unavailable, flag rather than substitute a biased default.

- **Homogeneity gate (mandatory).** Only pool studies similar enough in population, intervention, comparator, and outcome. Surface clinical diversity and require confirmation rather than silently combining unlike trials.
- **Core method.** Two-stage inverse-variance: per-study effect and SE, then weighted average. Pool ratio measures (RR, OR) on the log scale.
- **Effect measure.** Binary: prefer RR or OR; avoid risk difference. Continuous: mean difference for a shared scale, standardized mean difference for differing scales; check for skew; never mix log-transformed and untransformed data.
- **Model.** Default random-effects, REML for τ²; DerSimonian-Laird available. Never choose fixed vs. random from a heterogeneity test.
- **Confidence interval.** HKSJ with a t-distribution when τ² > 0 and >2 studies; Wald-type otherwise. Flag that HKSJ can be too wide, and Wald too narrow, with only 2–3 studies.
- **Heterogeneity.** Report χ² (read at P < 0.10, underpowered), I² with interpretation bands, and τ². I² bands: 0–40% may not be important, 30–60 moderate, 50–90 substantial, 75–100 considerable — avoid rigid thresholds. Add a prediction interval with ≥5 studies and no funnel asymmetry.
- **Rare events.** IV/DL are biased when events are rare. Below ~1% event rates, or with many zero-event arms, switch to Peto or Mantel-Haenszel without zero-cell correction, or flag. Exclude studies with no events in both arms. Never apply 0.5 corrections silently.
- **Sensitivity.** Leave-one-out. With 2–3 studies, compare Wald and HKSJ and report the difference.
- **Conversions.** SE↔SD, CI→SD etc. run in code, each logged as an assumption.
- **Out of scope:** subgroup analysis, meta-regression, network meta-analysis, time-to-event reconstruction.

## Risk of bias and certainty (RoB 2 and GRADE)
Core credibility steps, not preamble — pooling unappraised trials produces a confident wrong answer. Claude reads and judges, code computes what it can, a human confirms the load-bearing calls.
- **RoB 2, per trial.** Assess the five domains (randomization, deviations, missing outcome data, outcome measurement, selective reporting). Claude gives a first-pass judgment per domain with a source quote; a human confirms. Feeds a low-risk-only sensitivity analysis and the risk-of-bias input to GRADE.
- **GRADE, per outcome.** Rate certainty high/moderate/low/very low and output a Summary-of-Findings line. Inconsistency from I², imprecision from CI width and event counts, risk of bias from RoB 2. Claude judges indirectness and publication bias. Record the rationale for any downgrade.

## Deterministic validation gate
Plain code, not the model, runs before pooling. Anything that fails is flagged, not pooled.
- Events cannot exceed arm totals.
- Arm sizes must sum correctly.
- Percentages must match counts.

## Market intelligence layer
The same living evidence arranged as market intelligence (asset × indication × development stage, over time), assembled deterministically from CT.gov and joined to its pooled evidence — same provenance, living-update, and abstention discipline as the core. Code in `livemeta/core/ci/`; lenses include change feed, milestone radar, side-by-side compare, MoA clusters, company pipeline, and an NL chat router, surfaced over `/api/landscape/*` etc., matching MCP tools (`map_landscape`, `track_asset`, `compare_assets`, `company_pipeline`, `market_ask`), and web routes `/market` and `/company`.

## Tech stack
- Python. MCP Python SDK for the server.
- Pooling: R `metafor` (REML + HKSJ) via an `Rscript` subprocess bridge, not `rpy2` (sidesteps the arm64-Python / x86-R mismatch). Pure-Python `pymare` REML fallback, cross-validated in tests; select with `LIVEMETA_STATS_ENGINE`. `statsmodels.stats.meta_analysis` covers DerSimonian-Laird. Never hand-roll pooling. `scipy`/`numpy` for support.
- `matplotlib` for the forest plot. `httpx`/`requests` for the CT.gov, Europe PMC, and openFDA APIs.
- Web UI built against the reference designs in `stitch_livemeta_precision_evidence_system/`.

## Main risks and mitigations
- Extraction errors → prefer structured results, require provenance, validate before pooling.
- Wrong pooling → validated library, never model math.
- Scope creep → lock to one question and one outcome.
