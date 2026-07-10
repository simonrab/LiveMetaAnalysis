"""Optional matplotlib PNG forest plot for the CLI (`--plot PATH`).

Isolated here and imported lazily so nothing else in the CLI pulls in matplotlib:
only `--plot` touches it. Uses the headless Agg backend for deterministic,
display-free rendering. Fed by the same `PoolResult` as the ASCII forest in
`render.py`, so the terminal and the PNG agree.
"""

from __future__ import annotations

from ..core.schema import RATIO_MEASURES, PoolResult


def write_forest_png(
    pool: PoolResult,
    path: str,
    *,
    highlight: frozenset[str] | set[str] = frozenset(),
) -> None:
    """Render `pool` as a forest-plot PNG at `path`.

    Ratio measures use a log x-axis with the no-effect line at 1; continuous
    measures use a linear x-axis centred on 0. Marker size scales with each
    study's pool weight; the pooled estimate is drawn as a diamond. matplotlib is
    imported here (not at module top) so the CLI stays import-light unless
    `--plot` is used.
    """
    import matplotlib

    matplotlib.use("Agg")  # headless, deterministic, no display backend
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon

    rows = pool.studies
    ratio = pool.measure in RATIO_MEASURES
    nul = 1.0 if ratio else 0.0
    highlight = set(highlight)

    n = len(rows)
    fig, ax = plt.subplots(figsize=(8, max(2.0, 0.5 * n + 1.5)))

    # Study rows top-to-bottom; pooled diamond at y = -1 (below the studies).
    for i, r in enumerate(rows):
        y = n - i
        is_new = r.study_id in highlight
        color = "#c2410c" if is_new else "#334155"
        ax.plot([r.ci_low, r.ci_high], [y, y], "-", color=color, lw=1.3, zorder=2)
        ax.scatter(
            [r.effect], [y],
            s=30 + 12 * min(r.weight, 30),
            marker="s", color=color, zorder=3,
        )
        label = r.study_id + ("  (NEW)" if is_new else "")
        ax.text(-0.02, y, label, ha="right", va="center", transform=_blend(ax), fontsize=9)

    # Pooled diamond.
    yp = 0
    diamond = Polygon(
        [
            (pool.ci_low, yp),
            (pool.estimate, yp + 0.3),
            (pool.ci_high, yp),
            (pool.estimate, yp - 0.3),
        ],
        closed=True,
        facecolor="#c2410c",
        edgecolor="#c2410c",
        zorder=3,
    )
    ax.add_patch(diamond)
    ax.text(-0.02, yp, "Pooled (RE)", ha="right", va="center",
            transform=_blend(ax), fontsize=9, fontweight="bold")

    ax.axvline(nul, color="#94a3b8", lw=1, zorder=1)
    if ratio:
        ax.set_xscale("log")
    ax.set_ylim(-1, n + 1)
    ax.set_yticks([])
    ax.set_xlabel(f"{pool.measure.value} (95% CI)")
    ax.set_title("Forest plot")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _blend(ax):
    """A transform: x in axes fraction (for the left-margin labels), y in data."""
    import matplotlib.transforms as mtransforms

    return mtransforms.blended_transform_factory(ax.transAxes, ax.transData)
