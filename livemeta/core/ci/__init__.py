"""Competitive-intelligence layer.

The evidence layer (meta-analysis) answers "does drug X work, how certain."
This layer answers the *competitive* question around it: which assets are being
developed, at what stage, in which line of therapy, over time — and joins the two
so a competitive cell carries the living pooled evidence for that asset/outcome.

Same discipline as the rest of the tool: Claude reads messy free text into
structured events, deterministic code reconciles/dedups/time-orders and enforces
"no claim without a source snippet", and the layer abstains (flags conflicts)
rather than inventing a stage it cannot source.
"""
