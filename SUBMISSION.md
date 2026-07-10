# Living Meta-Analysis Tool — Submission

## Project description

**Competitive intelligence in pharma tells you the shape of a race (who's developing what, in which indication, at what stage) but not who's actually winning. That answer only comes from pooling the trial evidence, and that evidence is out of date the day it publishes.** So we built the two halves as one system: a living meta-analysis engine that produces the winning-or-not answer, feeding a competitive landscape that stays current because the evidence underneath it does.

**The engine.** Ask a clinical question in PICO form; the tool finds the trials, extracts every effect with full provenance, appraises it (RoB 2 + GRADE), and pools it into a current, auditable answer: forest plot, heterogeneity, plain-language summary. It re-runs itself the moment a new trial reads out and flags whether the conclusion changed. It earns trust by dividing the labour: **Claude reads and structures the evidence; deterministic code does every number.** A validation gate and a Cochrane-aligned stats library (random-effects, REML, HKSJ) do all the pooling. The model never computes an estimate, every value traces to its source snippet, and the tool **abstains rather than inventing precision** when data is thin.

**The landscape.** Those living answers roll up into a board mapping assets × indications × stage × time. Unlike an ordinary CI dashboard, every cell is backed by that same pooled, auditable evidence. You don't just see that a race exists; you see who's ahead on the actual data, defensible line by line, and it updates itself as new readouts land. One new trial moves both the pooled estimate and the competitive standing at once, which is exactly why they can't be two separate tools.

**Why it matters / what we found.** Medical-affairs, HEOR, and clinical-dev teams can't keep evidence current and can't defend an answer they can't trace. We validated against a known truth: GLP-1 agonists vs. placebo for MACE, published HR ~0.86 (0.80–0.93), 8 trials (Sattar 2021). The tool reproduces it from structured data, then in the live demo we inject the 8th trial and watch the estimate and conclusion update on their own. Shipped as an MCP server (19 tools) plus a full web platform, built test-first: 383 backend + 40 frontend tests, all green.

---

## 3-minute demo video script

**[0:00–0:20] The problem**
> "A meta-analysis is the top of the evidence pyramid for clinical decisions — and it's out of date the day it publishes. Refreshing one is slow, manual, and expensive. So the teams who most depend on current evidence are always working from a stale answer. We built a living meta-analysis tool that fixes that, and does it in a way a regulated team can actually trust."

**[0:20–0:45] The design principle (the trust story)**
> "The whole thing rests on one rule: divide the labour by what each part is reliable at. Claude reads and structures the evidence — it's strong at reading, weak at arithmetic. A validated statistics library does all the pooling. The model never touches a pooled number. And every value carries its source trial and the exact snippet it came from."
*(On screen: split diagram — Claude reads / code computes.)*

**[0:45–1:30] The pipeline, end to end**
> "Here's a real question: do GLP-1 receptor agonists reduce major adverse cardiovascular events? Claude parses it into PICO, pulls eight cardiovascular outcome trials from ClinicalTrials.gov, and extracts arm-level results."
*(Ask screen → pipeline running → evidence ledger.)*
> "This is the evidence ledger. Every extraction links to its snippet — click any number and you see where it came from. Before anything pools, a deterministic gate checks the numbers: events can't exceed arm totals, arms must sum, percentages must match counts. Anything that fails gets flagged, not pooled."
*(Show a provenance snippet, then the validation gate.)*
> "Claude does a first-pass RoB 2 and GRADE read — with a quote behind every judgment — and a human confirms the load-bearing calls."

**[1:30–2:10] The answer**
> "Then the validated library pools it — random-effects, REML, HKSJ interval, exactly the Cochrane Handbook method. Here's the forest plot. Pooled hazard ratio: 0.86, confidence interval 0.80 to 0.93. That matches the published Sattar 2021 meta-analysis — so you can sanity-check it against known truth. Alongside it: I² heterogeneity, a funnel plot with Egger's test, a leave-one-out sensitivity check, a PRISMA record-flow, and a plain-language summary. And when the data is thin or heterogeneity is high, the tool abstains instead of inventing precision."
*(Report screen: forest plot, funnel, PRISMA.)*

**[2:10–2:50] The living moment**
> "Now the part that makes it *living*. This review was built when only seven trials had read out. Watch what happens when the eighth — AMPLITUDE-O — lands."
*(Click inject / check_updates.)*
> "The tool re-runs automatically, re-pools, and diffs against the previous version — the estimate updates, and it flags whether the conclusion changed. Your evidence base never goes stale, and every version is auditable."

**[2:50–3:00] Close**
> "Claude reads. Code computes. Everything traces to a source. That's a meta-analysis that stays current — and one you can defend line by line. Built with Claude Code, test-first: 383 backend and 40 frontend tests, all green."
